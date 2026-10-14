<script>
	import * as d3 from 'd3';
	import { fmtAcres, fmtInt, fmtCompact } from './format.js';
	import { GROUPS, OWNERS, groupOf, groupCss, ownerCss } from './colors.js';

	let {
		spaces,
		highlightId = null,
		selection = null,
		hiddenGroups = new Set(),
		onpick = null,
		// dashboard 2: color by ownership, report hover, and fade dots that miss the ownership/category filter
		colorMode = 'type',
		onhover = null,
		filter = null,
		tipHint = 'Click to center the map here',
		instructions = null,
		statusHint = 'Use “Select area” on the map to filter them.'
	} = $props();

	const W = 760;
	const M = { l: 112, r: 28, top: 8, axis: 40 };
	const CITIES = ['Boston', 'Cambridge', 'Somerville'];
	const BAND = { Boston: 250, Cambridge: 170, Somerville: 120 };

	function build(spaces) {
		const feats = spaces.features.map((f) => ({ ...f.properties, group: groupOf(f.properties.category) }));
		const maxPeople = d3.max(feats, (d) => d.pop_500m);
		const x = d3.scaleLinear().domain([0, Math.ceil(maxPeople / 10000) * 10000]).range([M.l, W - M.r]);
		const r = d3.scaleSqrt().domain([0, d3.max(feats, (d) => d.area_m2)]).range([2, 26]);

		let y0 = M.top;
		const rows = [];
		const nodes = [];
		for (const city of CITIES) {
			const h = BAND[city];
			const cy = y0 + h / 2;
			const items = feats
				.filter((d) => d.city === city)
				.sort((a, b) => b.area_m2 - a.area_m2)
				.map((d) => ({ d, r: r(d.area_m2), tx: x(d.pop_500m), x: x(d.pop_500m), y: cy }));
			d3.forceSimulation(items)
				.force('x', d3.forceX((n) => n.tx).strength(1))
				.force('y', d3.forceY(cy).strength(0.07))
				.force('collide', d3.forceCollide((n) => n.r + 0.8).strength(0.9))
				.stop()
				.tick(220);
			for (const n of items) n.y = Math.max(y0 + n.r + 1, Math.min(y0 + h - n.r - 1, n.y));
			rows.push({ city, y0, h, cy, n: items.length, ids: items.map((n) => n.d.id) });
			nodes.push(...items);
			y0 += h;
		}
		const H = y0 + M.axis;
		return {
			x,
			r,
			rows,
			nodes,
			byId: new Map(nodes.map((n) => [n.d.id, n])),
			H,
			delaunay: d3.Delaunay.from(nodes, (n) => n.x, (n) => n.y),
			ticks: x.ticks(8),
			top: feats.slice().sort((a, b) => b.pop_500m - a.pop_500m).slice(0, 12)
		};
	}
	const model = $derived(build(spaces));

	// state of each dot: hidden by the category filter, outside the map selection, or active
	const hidden = (d) => hiddenGroups.has(d.group);
	const outside = (d) =>
		(selection && !selection.ids.has(d.id)) ||
		(filter && ((filter.owner && d.owner !== filter.owner) || (filter.category && d.category !== filter.category)));

	const rowStats = $derived(
		model.rows.map((row) => {
			const act = row.ids
				.map((id) => model.byId.get(id).d)
				.filter((d) => !hidden(d) && !outside(d));
			return { ...row, k: act.length, median: act.length ? d3.median(act, (d) => d.pop_500m) : null };
		})
	);
	const activeCount = $derived(rowStats.reduce((s, r) => s + r.k, 0));

	const hl = $derived(highlightId ? model.byId.get(highlightId) : null);

	let wrap = $state();
	let svg = $state();
	let hover = $state(null);
	let tip = $state({ left: 0, top: 0, flip: false });
	$effect(() => {
		onhover?.(hover ? hover.d.id : null);
	});

	function onMove(e) {
		const rect = svg.getBoundingClientRect();
		const k = W / rect.width;
		const px = (e.clientX - rect.left) * k;
		const py = (e.clientY - rect.top) * k;
		const n = model.nodes[model.delaunay.find(px, py)];
		if (n && !hidden(n.d) && Math.hypot(n.x - px, n.y - py) <= n.r + 7) {
			hover = n;
			const w = wrap.getBoundingClientRect();
			tip = { left: e.clientX - w.left, top: e.clientY - w.top, flip: e.clientX - w.left > w.width - 290 };
		} else hover = null;
	}

	function kind(d) {
		return d.owner === 'Unknown' ? 'unknown' : d.private_owned ? 'private' : 'public';
	}
</script>

<div class="wrap" bind:this={wrap}>
	<ul class="how" aria-label="How to use the dot plot">
		{#if instructions}
			{#each instructions as line (line)}
				<li>{@html line}</li>
			{/each}
		{:else}
			<li><b>Hover</b> a dot for the space’s details; <b>click</b> a dot to center the map on that space.</li>
			<li>The <b>ringed, labeled</b> dot is the space currently at the center of the map.</li>
			<li>Faded dots are outside the area you selected on the map, or hidden by the category buttons above.</li>
		{/if}
	</ul>

	<p class="status" aria-live="polite">
		{#if filter && (filter.owner || filter.category)}
			Showing <strong>{activeCount}</strong> of {model.nodes.length} spaces:
			{[filter.owner && `owner = ${filter.owner}`, filter.category && `type = ${filter.category}`].filter(Boolean).join(' · ')}.
		{:else if selection}
			Showing <strong>{activeCount}</strong> spaces inside the area selected on the map.
		{:else}
			Showing <strong>{activeCount}</strong> spaces. {statusHint}
		{/if}
	</p>

	<svg
		bind:this={svg}
		viewBox="0 0 {W} {model.H}"
		role="img"
		aria-label="Dot plot: for each city, every public space placed by the number of people living within 500 m; dot size is the space's area."
		class:pick={hover && onpick}
		onpointermove={onMove}
		onpointerleave={() => (hover = null)}
		onclick={() => hover && onpick?.(hover.d.id)}
	>
		{#each model.ticks as tk (tk)}
			<line class="grid" x1={model.x(tk)} x2={model.x(tk)} y1={M.top} y2={model.H - M.axis} />
			<text class="tick-label" x={model.x(tk)} y={model.H - M.axis + 18} text-anchor="middle">{fmtCompact(tk)}</text>
		{/each}
		<text class="axis-title" x={(M.l + W - M.r) / 2} y={model.H - 6} text-anchor="middle">
			People living within 500 m of the space (2020 census)
		</text>
		{#each rowStats as row, i (row.city)}
			{#if i > 0}
				<line class="sep" x1="0" x2={W} y1={row.y0} y2={row.y0} />
			{/if}
			<text class="row-label" x="6" y={row.cy - 4}>{row.city}</text>
			<text class="row-sub" x="6" y={row.cy + 12}>
				{row.k === row.n ? `${row.n} spaces` : `${row.k} of ${row.n} spaces`}
			</text>
			<text class="row-sub" x="6" y={row.cy + 26}>
				{row.median == null ? 'no spaces' : `median ${fmtCompact(row.median)}`}
			</text>
			{#if row.median != null}
				<line class="median" x1={model.x(row.median)} x2={model.x(row.median)} y1={row.y0 + 4} y2={row.y0 + row.h - 4} />
			{/if}
		{/each}
		{#each model.nodes as n (n.d.id)}
			<circle
				class="dot {kind(n.d)}"
				class:faded={outside(n.d)}
				class:off={hidden(n.d)}
				class:hover={hover === n}
				cx={n.x}
				cy={n.y}
				r={n.r}
				style:--c={colorMode === 'owner' ? ownerCss[n.d.owner] : groupCss[n.d.group]}
			/>
		{/each}
		{#if hl}
			{@const left = hl.x < 220}
			{@const right = hl.x > W - 260}
			<circle class="hl-ring" cx={hl.x} cy={hl.y} r={hl.r + 5} />
			<text
				class="hl-label"
				x={hl.x + (left ? hl.r + 9 : right ? -(hl.r + 9) : 0)}
				y={hl.y - hl.r - 11}
				text-anchor={left ? 'start' : right ? 'end' : 'middle'}
			>
				{hl.d.name} · {fmtCompact(hl.d.pop_500m)} people
			</text>
		{/if}
	</svg>

	{#if hover}
		{@const d = hover.d}
		<div class="tip" style:left="{tip.flip ? tip.left - 14 : tip.left + 14}px" style:top="{tip.top + 14}px" style:transform={tip.flip ? 'translateX(-100%)' : 'none'} role="tooltip">
			<strong>{d.name}</strong>
			<div class="t-sub">{d.city} · {d.category}</div>
			<div><strong>{fmtInt(d.pop_500m)}</strong> people within 500 m</div>
			<div>{fmtAcres(d.area_acres)} · {d.owner}{d.owner_name && d.owner_name !== d.owner ? ` (${d.owner_name})` : ''}</div>
			{#if tipHint}<div class="t-act">{tipHint}</div>{/if}
		</div>
	{/if}

	{#if colorMode === 'owner'}
		<div class="legend">
			<span class="lgt">Color = owner</span>
			{#each OWNERS as o (o.key)}
				<span class="lg"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" class="dot public" style:--c={o.css} /></svg> {o.label}</span>
			{/each}
		</div>
		<div class="legend">
			<span class="lgt">Fill</span>
			<span class="lg"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" class="dot public" style:--c="var(--ink-2)" /></svg> Publicly owned</span>
			<span class="lg"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" class="dot private" style:--c="var(--ink-2)" /></svg> Private / nonprofit, open to the public</span>
			{@render sizeLegend()}
		</div>
	{:else}
		<div class="legend">
			<span class="lgt">Color = type</span>
			{#each GROUPS as g (g.key)}
				<span class="lg"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" class="dot public" style:--c={g.css} /></svg> {g.label}</span>
			{/each}
		</div>
		<div class="legend">
			<span class="lgt">Fill = ownership</span>
			<span class="lg"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" class="dot public" style:--c="var(--ink-2)" /></svg> Publicly owned</span>
			<span class="lg"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" class="dot private" style:--c="var(--ink-2)" /></svg> Private / nonprofit, open to the public</span>
			<span class="lg"><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="5.5" class="dot unknown" style:--c="var(--ink-2)" /></svg> Owner unknown</span>
			{@render sizeLegend()}
		</div>
	{/if}

	{#snippet sizeLegend()}
		<span class="lg sizes">
			Size = area:
			<svg width="92" height="34" aria-hidden="true">
				{#each [0.1, 10, 100] as ac, i (ac)}
					<circle cx={10 + i * 30} cy="17" r={model.r(ac * 4046.86)} class="size" />
				{/each}
			</svg>
			0.1 · 10 · 100 ac
		</span>
	{/snippet}

	<details>
		<summary>Table view: 12 spaces with the most people nearby</summary>
		<table>
			<thead><tr><th>Space</th><th>City</th><th>Category</th><th>Owner</th><th class="num">Acres</th><th class="num">People ≤ 500 m</th></tr></thead>
			<tbody>
				{#each model.top as d (d.id)}
					<tr><td>{d.name}</td><td>{d.city}</td><td>{d.category}</td><td>{d.owner}</td><td class="num">{d.area_acres.toFixed(1)}</td><td class="num">{fmtInt(d.pop_500m)}</td></tr>
				{/each}
			</tbody>
		</table>
	</details>
</div>

<style>
	.wrap { position: relative; }
	svg { width: 100%; height: auto; display: block; }
	svg.pick { cursor: pointer; }
	.how { margin: 0 0 8px; padding: 8px 12px 8px 28px; font-size: 0.78rem; color: var(--ink-2); background: var(--surface-2); border-radius: 8px; }
	.how li + li { margin-top: 3px; }
	.status { margin: 0 0 4px; font-size: 0.85rem; color: var(--ink-2); }
	.grid { stroke: var(--line); stroke-width: 1; }
	.sep { stroke: var(--line); stroke-width: 1; }
	.median { stroke: var(--ink-3); stroke-width: 1; stroke-dasharray: 3 3; opacity: 0.8; }
	.tick-label { fill: var(--ink-3); font-size: 11px; }
	.axis-title { fill: var(--ink-2); font-size: 12px; }
	.row-label { fill: var(--ink); font-size: 15px; font-weight: 700; font-family: var(--font-title); }
	.row-sub { fill: var(--ink-3); font-size: 11px; }
	.dot { stroke-width: 1.5; transition: opacity 0.15s; }
	.dot.public { fill: var(--c); stroke: var(--surface); fill-opacity: 0.85; }
	.dot.private { fill: var(--surface); stroke: var(--c); }
	.dot.unknown { fill: var(--c); fill-opacity: 0.35; stroke: var(--c); stroke-width: 1; }
	.dot.faded { opacity: 0.12; }
	.dot.off { opacity: 0.04; }
	.dot.hover { stroke: var(--ink); stroke-width: 2.5; }
	.hl-ring { fill: none; stroke: var(--ink); stroke-width: 2.5; pointer-events: none; }
	.hl-label {
		fill: var(--ink); font-size: 12px; font-weight: 700; paint-order: stroke; stroke: var(--surface);
		stroke-width: 4px; stroke-linejoin: round; pointer-events: none;
	}
	.size { fill: none; stroke: var(--ink-2); stroke-width: 1.2; }
	.tip {
		position: absolute; pointer-events: none; z-index: 3; width: max-content; max-width: 260px; padding: 8px 10px;
		background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 8px;
		box-shadow: 0 4px 14px rgb(0 0 0 / 0.15); font-size: 0.8rem; line-height: 1.35;
	}
	.t-sub { color: var(--ink-2); }
	.t-act { margin-top: 4px; color: var(--ink-3); font-size: 0.72rem; }
	.legend { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 16px; margin-top: 8px; font-size: 0.8rem; color: var(--ink-2); }
	.lgt { font-weight: 700; color: var(--ink); }
	.lg { display: inline-flex; align-items: center; gap: 6px; }
	.lg svg { width: auto; display: inline-block; }
	details { margin-top: 10px; font-size: 0.8rem; color: var(--ink-2); }
	summary { cursor: pointer; }
	table { border-collapse: collapse; width: 100%; margin-top: 6px; }
	th, td { text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--line); }
	.num { text-align: right; font-variant-numeric: tabular-nums; }
</style>
