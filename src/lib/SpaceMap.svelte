<script>
	import { onMount, untrack } from 'svelte';
	import * as d3 from 'd3';
	import StripPlot from './StripPlot.svelte';
	import { fmtArea, fmtAcres, fmtInt, ordinal } from './format.js';
	import { groupOf, groupCss } from './colors.js';

	let {
		spaces,
		boundaries,
		water,
		focusId = $bindable(null),
		jumpRequest = { id: null, n: 0 },
		selection = null,
		hiddenGroups = new Set(),
		onselect = () => {}
	} = $props();

	const W = 600;
	const H = 540;
	const ACCESS_M = 500;

	function buildModel(spaces, boundaries) {
		const proj = d3.geoMercator().fitExtent(
			[
				[24, 24],
				[W - 24, H - 24]
			],
			boundaries
		);
		const path = d3.geoPath(proj);
		// 500 m expressed in "world" pixels (the map's unzoomed coordinate system).
		const lat0 = 42.355;
		const dlon = ACCESS_M / (111320 * Math.cos((lat0 * Math.PI) / 180));
		const r0 = Math.abs(proj([-71.09 + dlon, lat0])[0] - proj([-71.09, lat0])[0]);

		const feats = spaces.features.map((f) => {
			const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
			const [[x0, y0], [x1, y1]] = path.bounds(f);
			return {
				id: f.properties.id,
				p: f.properties,
				group: groupOf(f.properties.category),
				d: path(f),
				rings: polys.map((poly) => poly[0].map((c) => proj(c))),
				bbox: [x0, y0, x1, y1],
				at: proj([f.properties.lon, f.properties.lat])
			};
		});
		return {
			proj,
			scale: proj.scale(),
			r0,
			feats,
			byId: new Map(feats.map((f) => [f.id, f])),
			options: feats.slice().sort((a, b) => a.p.name.localeCompare(b.p.name)),
			boundaryD: path(boundaries),
			areas: feats.map((f) => f.p.area_acres),
			people: feats.map((f) => f.p.pop_500m)
		};
	}
	const model = $derived(buildModel(spaces, boundaries));
	const waterD = $derived(d3.geoPath(model.proj)(water));

	function segDist(px, py, a, b) {
		const dx = b[0] - a[0];
		const dy = b[1] - a[1];
		const l2 = dx * dx + dy * dy;
		let u = l2 ? ((px - a[0]) * dx + (py - a[1]) * dy) / l2 : 0;
		u = Math.max(0, Math.min(1, u));
		return Math.hypot(px - (a[0] + u * dx), py - (a[1] + u * dy));
	}

	/** The space under (x, y), or else the nearest one within `snap` world px. */
	function findSpace(feats, x, y, snap) {
		let best = null;
		let bestD = Infinity;
		for (const f of feats) {
			const [x0, y0, x1, y1] = f.bbox;
			if (x < x0 - snap || x > x1 + snap || y < y0 - snap || y > y1 + snap) continue;
			let inside = false;
			let d = Infinity;
			for (const ring of f.rings) {
				if (!inside && d3.polygonContains(ring, [x, y])) inside = true;
				for (let i = 1; i < ring.length; i++) d = Math.min(d, segDist(x, y, ring[i - 1], ring[i]));
			}
			if (inside) d = -f.p.area_m2; // containing spaces win; smallest container first
			if (d < bestD && (inside || d <= snap)) {
				best = f;
				bestD = d;
			}
		}
		return best;
	}

	let svg = $state();
	let t = $state.raw(d3.zoomIdentity);
	let zoomBehavior;
	let mode = $state('pan'); // 'pan' | 'select'
	let dark = $state(false);

	const focus = $derived.by(() => {
		const [x, y] = t.invert([W / 2, H / 2]);
		return findSpace(model.feats, x, y, Math.max(model.r0 * 0.3, 22 / t.k));
	});
	$effect(() => {
		focusId = focus ? focus.id : null;
	});

	function jumpTo(f, animate = true) {
		const [x0, y0, x1, y1] = f.bbox;
		// fit the space (about 110 px) but keep the whole 500 m halo inside the view
		const k = Math.max(4, Math.min(110 / Math.max(x1 - x0, y1 - y0, 1e-6), 170 / model.r0));
		const next = d3.zoomIdentity.translate(W / 2 - k * f.at[0], H / 2 - k * f.at[1]).scale(k);
		const sel = d3.select(svg);
		(animate ? sel.transition().duration(700) : sel).call(zoomBehavior.transform, next);
	}

	$effect(() => {
		const { id, n } = jumpRequest;
		if (!n || !zoomBehavior) return;
		untrack(() => {
			const f = model.byId.get(id);
			if (f) jumpTo(f);
		});
	});

	onMount(() => {
		zoomBehavior = d3
			.zoom()
			.scaleExtent([1, 40])
			.translateExtent([
				[-40, -40],
				[W + 40, H + 40]
			])
			.filter((e) => (mode === 'select' ? e.type === 'wheel' : (!e.ctrlKey || e.type === 'wheel') && !e.button))
			.on('zoom', (e) => (t = e.transform));
		d3.select(svg).call(zoomBehavior);
		const wanted = new URLSearchParams(location.search).get('space') ?? 'Copley Square';
		jumpTo(model.feats.find((f) => f.p.name === wanted) ?? model.feats[0], false);

		const mq = matchMedia('(prefers-color-scheme: dark)');
		const root = document.documentElement;
		const sync = () => {
			const th = root.dataset.theme;
			dark = th === 'dark' || (th !== 'light' && mq.matches);
		};
		sync();
		mq.addEventListener('change', sync);
		const mo = new MutationObserver(sync);
		mo.observe(root, { attributes: true, attributeFilter: ['data-theme'] });
		return () => {
			mq.removeEventListener('change', sync);
			mo.disconnect();
		};
	});

	let query = $state('');
	function onSearch() {
		const f = model.options.find((o) => `${o.p.name} (${o.p.city})` === query);
		if (f) jumpTo(f);
	}

	// ---- OpenStreetMap raster basemap, muted with a CSS filter (see .tiles) ----
	const tiles = $derived.by(() => {
		const K = model.scale * t.k;
		const z = Math.max(0, Math.min(19, Math.round(Math.log2((2 * Math.PI * K) / 256) + 0.35)));
		const n = 2 ** z;
		const [wx0, wy0] = t.invert([0, 0]);
		const [wx1, wy1] = t.invert([W, H]);
		const [lon0, lat0] = model.proj.invert([wx0, wy0]);
		const [lon1, lat1] = model.proj.invert([wx1, wy1]);
		const tx = (lon) => Math.floor(((lon + 180) / 360) * n);
		const ty = (lat) => {
			const r = (lat * Math.PI) / 180;
			return Math.floor(((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * n);
		};
		const nw = (x, y) => [
			(x / n) * 360 - 180,
			(Math.atan(Math.sinh(Math.PI * (1 - (2 * y) / n))) * 180) / Math.PI
		];
		const out = [];
		for (let x = Math.max(0, tx(lon0)); x <= Math.min(n - 1, tx(lon1)); x++) {
			for (let y = Math.max(0, ty(lat0)); y <= Math.min(n - 1, ty(lat1)); y++) {
				const a = t.apply(model.proj(nw(x, y)));
				const b = t.apply(model.proj(nw(x + 1, y + 1)));
				out.push({
					key: `${z}/${x}/${y}`,
					href: `https://tile.openstreetmap.org/${z}/${x}/${y}.png`,
					x: a[0],
					y: a[1],
					w: b[0] - a[0] + 0.7,
					h: b[1] - a[1] + 0.7
				});
			}
		}
		return out.length > 48 ? [] : out;
	});

	// ---- brushing ----
	let dragStart = null;
	function worldPoint(e) {
		return t.invert(d3.pointer(e, svg));
	}
	function onDown(e) {
		if (mode !== 'select' || e.button !== 0) return;
		svg.setPointerCapture(e.pointerId);
		dragStart = worldPoint(e);
		onselect(null);
	}
	function onMove(e) {
		if (!dragStart) return;
		const [x, y] = worldPoint(e);
		const rect = {
			x0: Math.min(dragStart[0], x),
			y0: Math.min(dragStart[1], y),
			x1: Math.max(dragStart[0], x),
			y1: Math.max(dragStart[1], y)
		};
		const ids = new Set(
			model.feats
				.filter((f) => f.at[0] >= rect.x0 && f.at[0] <= rect.x1 && f.at[1] >= rect.y0 && f.at[1] <= rect.y1)
				.map((f) => f.id)
		);
		onselect({ rect, ids });
	}
	function onUp() {
		if (!dragStart) return;
		dragStart = null;
		// a click without dragging clears the selection
		if (selection && (selection.rect.x1 - selection.rect.x0) * t.k < 4) onselect(null);
	}

	const barPx = $derived(model.r0 * t.k);
	const p = $derived(focus?.p);
	const ring = $derived.by(() => {
		if (!focus) return null;
		const [x0, y0, x1, y1] = focus.bbox;
		if (Math.max(x1 - x0, y1 - y0) * t.k >= 18) return null;
		const [cx, cy] = t.apply(focus.at);
		return { cx, cy };
	});
	const shown = (f) => !hiddenGroups.has(f.group);
</script>

<div class="map-card">
	<div class="toolbar">
		<div class="modes" role="group" aria-label="Map mode">
			<button class:on={mode === 'pan'} onclick={() => (mode = 'pan')} aria-pressed={mode === 'pan'}>
				<span aria-hidden="true">✥</span> Pan
			</button>
			<button class:on={mode === 'select'} onclick={() => (mode = 'select')} aria-pressed={mode === 'select'}>
				<span aria-hidden="true">▭</span> Select area
			</button>
		</div>
		{#if selection}
			<button class="clear" onclick={() => onselect(null)}>Clear selection ({selection.ids.size})</button>
		{/if}
		<div class="search">
			<label for="jump">Jump to</label>
			<input id="jump" list="space-list" placeholder="space name…" bind:value={query} onchange={onSearch} />
			<datalist id="space-list">
				{#each model.options as o (o.id)}
					<option value="{o.p.name} ({o.p.city})"></option>
				{/each}
			</datalist>
		</div>
	</div>

	<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
	<svg
		bind:this={svg}
		viewBox="0 0 {W} {H}"
		role="img"
		aria-label="Map of public spaces. The space under the center crosshair is summarized below the map."
		tabindex="0"
		class:selecting={mode === 'select'}
		onpointerdown={onDown}
		onpointermove={onMove}
		onpointerup={onUp}
	>
		<rect class="bg" width={W} height={H} />
		<g transform={t.toString()}>
			<path class="water" d={waterD} />
		</g>
		<g class="tiles" class:dark>
			{#each tiles as tl (tl.key)}
				<image href={tl.href} x={tl.x} y={tl.y} width={tl.w} height={tl.h} preserveAspectRatio="none" />
			{/each}
		</g>
		<g transform={t.toString()}>
			<path class="boundary" d={model.boundaryD} />
			{#if focus}
				<path class="band" d={focus.d} style:stroke-width="{model.r0 * 2}px" />
			{/if}
			{#each model.feats as f (f.id)}
				{#if shown(f)}
					<path
						class="space"
						class:dim={selection && !selection.ids.has(f.id)}
						class:sel={selection && selection.ids.has(f.id)}
						d={f.d}
						style:--c={groupCss[f.group]}
					/>
				{/if}
			{/each}
			{#if focus}
				<path class="focus" d={focus.d} style:--c={groupCss[focus.group]} />
			{/if}
			{#if selection}
				<rect
					class="brush"
					x={selection.rect.x0}
					y={selection.rect.y0}
					width={selection.rect.x1 - selection.rect.x0}
					height={selection.rect.y1 - selection.rect.y0}
				/>
			{/if}
		</g>
		{#if ring}
			<circle class="ring" cx={ring.cx} cy={ring.cy} r="13" />
		{/if}
		<g class="reticle" transform="translate({W / 2},{H / 2})">
			<line x1="-9" x2="9" y1="0" y2="0" />
			<line x1="0" x2="0" y1="-9" y2="9" />
		</g>
		<g class="scale" transform="translate(16,{H - 18})">
			<line x1="0" x2={barPx} y1="0" y2="0" />
			<line x1="0" x2="0" y1="-4" y2="4" />
			<line x1={barPx} x2={barPx} y1="-4" y2="4" />
			<text x="0" y="-8">{ACCESS_M} m</text>
		</g>
		<text class="attrib" x={W - 6} y={H - 6} text-anchor="end">© OpenStreetMap contributors</text>
	</svg>

	<ul class="how" aria-label="How to use the map">
		<li><b>Pan</b> mode: drag to move the map; scroll or pinch to zoom. The space under the <b>+</b> is summarized below and highlighted in the dot plot.</li>
		<li><b>Select area</b> mode: drag a rectangle to filter the dot plot to the spaces whose center falls inside it. Click the map or “Clear selection” to reset.</li>
		<li>The halo around the highlighted space is the 500 m zone used to count nearby people.</li>
	</ul>

	<div class="summary" aria-live="polite">
		{#if p}
			<h3>{p.name}</h3>
			<p class="meta">{p.city} · {p.category}</p>
			<p class="figs">
				<strong>{fmtArea(p.area_m2)}</strong> <span class="sub">({fmtAcres(p.area_acres)})</span>
				<span class="sep">|</span>
				<strong>{ordinal(p.rank_all)}</strong>
				<span class="sub">largest of {model.feats.length} spaces</span>
			</p>
			<p class="owner">
				Owner: <strong>{p.owner}</strong>{#if p.owner_name && p.owner_name !== p.owner}
					<span class="sub">&nbsp;· {p.owner_name}</span>{/if}
				<span class="sep">|</span>
				<strong>{fmtInt(p.pop_500m)}</strong> <span class="sub">people within 500 m</span>
			</p>
			<div class="strips">
				<StripPlot
					title="Area (acres, log scale)"
					values={model.areas}
					value={p.area_acres}
					scale="log"
					valueLabel={fmtAcres(p.area_acres)}
					ticks={[
						{ v: 0.01, label: '0.01' },
						{ v: 0.1, label: '0.1' },
						{ v: 1, label: '1' },
						{ v: 10, label: '10' },
						{ v: 100, label: '100' }
					]}
				/>
				<StripPlot
					title="People within 500 m"
					values={model.people}
					value={p.pop_500m}
					valueLabel={fmtInt(p.pop_500m)}
					ticks={[0, 20000, 40000, 60000, 80000].map((v) => ({ v, label: v ? `${v / 1000}k` : '0' }))}
				/>
			</div>
		{:else}
			<h3 class="empty">No space under the crosshair</h3>
			<p class="meta">Pan the map until a park, square or plaza is at the center.</p>
		{/if}
	</div>
</div>

<style>
	.map-card { display: flex; flex-direction: column; gap: 8px; }
	.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; font-size: 0.85rem; color: var(--ink-2); }
	.modes { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
	.modes button, .clear {
		font: inherit; font-weight: 600; padding: 6px 12px; border: 0; background: var(--surface);
		color: var(--ink-2); cursor: pointer;
	}
	.modes button + button { border-left: 1px solid var(--line); }
	.modes button.on { background: var(--ink); color: var(--surface); }
	.clear { border: 1px solid var(--line); border-radius: 8px; }
	.search { display: flex; align-items: center; gap: 8px; margin-left: auto; min-width: 0; }
	.search input {
		width: 190px; min-width: 0; padding: 6px 10px; border: 1px solid var(--line); border-radius: 6px;
		background: var(--surface); color: var(--ink); font: inherit;
	}
	svg {
		width: 100%; height: auto; display: block; border: 1px solid var(--line); border-radius: 8px;
		cursor: grab; touch-action: none; user-select: none;
	}
	svg:active { cursor: grabbing; }
	svg.selecting, svg.selecting:active { cursor: crosshair; }
	.bg { fill: var(--surface-2); }
	.water { fill: var(--water); }
	.tiles { pointer-events: none; opacity: 0.42; filter: grayscale(0.95) contrast(0.7) brightness(1.2); }
	.tiles.dark { opacity: 0.4; filter: invert(1) hue-rotate(180deg) grayscale(0.95) contrast(0.7) brightness(0.8); }
	.boundary { fill: none; stroke: var(--boundary); stroke-width: 1.2; stroke-dasharray: 5 3; vector-effect: non-scaling-stroke; }
	.space {
		fill: var(--c); fill-opacity: 0.5; stroke: var(--c); stroke-width: 0.8; vector-effect: non-scaling-stroke;
	}
	.space.dim { fill-opacity: 0.08; stroke-opacity: 0.25; }
	.space.sel { fill-opacity: 0.75; stroke: var(--ink); stroke-width: 1; }
	.band { fill: var(--ink); stroke: var(--ink); stroke-linejoin: round; opacity: 0.07; }
	.focus { fill: var(--c); stroke: var(--ink); stroke-width: 2.2; vector-effect: non-scaling-stroke; fill-opacity: 0.95; }
	.brush { fill: var(--ink); fill-opacity: 0.06; stroke: var(--ink); stroke-width: 1.5; stroke-dasharray: 5 3; vector-effect: non-scaling-stroke; }
	.ring { fill: none; stroke: var(--ink); stroke-width: 2.5; }
	.reticle line { stroke: var(--ink); stroke-width: 1.5; opacity: 0.75; }
	.scale line { stroke: var(--ink-2); stroke-width: 1.5; }
	.scale text, .attrib { fill: var(--ink-2); font-size: 11px; paint-order: stroke; stroke: var(--surface); stroke-width: 3px; }
	.attrib { font-size: 9px; }
	.how { margin: 0; padding: 8px 12px 8px 28px; font-size: 0.78rem; color: var(--ink-2); background: var(--surface-2); border-radius: 8px; }
	.how li + li { margin-top: 3px; }
	.summary { min-height: 300px; padding-top: 4px; }
	.summary h3 { font-size: 1.4rem; }
	.empty { color: var(--ink-2); }
	.meta { margin: 2px 0 8px; color: var(--ink-2); font-size: 0.9rem; }
	.figs, .owner { margin: 2px 0; font-size: 1rem; }
	.sub { color: var(--ink-2); font-size: 0.85rem; }
	.sep { color: var(--ink-3); margin: 0 6px; }
	.strips { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 12px; }
	@media (max-width: 560px) { .strips { grid-template-columns: 1fr; } .search { margin-left: 0; } }
</style>
