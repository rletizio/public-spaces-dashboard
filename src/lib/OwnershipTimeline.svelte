<script>
	import * as d3 from 'd3';
	import { sankey, sankeyLinkHorizontal } from 'd3-sankey';
	import { OWNERS, CATEGORIES, ownerCss } from './colors.js';
	import { fmtInt } from './format.js';

	// hoverId: space hovered in the dot plot (highlights its owner and type here)
	// filter / onfilter: {owner, category} chosen by clicking here (filters the dot plot)
	let { spaces, hoverId = null, filter = { owner: null, category: null }, onfilter = () => {} } = $props();

	const W = 860;
	const H = 480;
	const TOP = 56;
	const BOT = H - 46;
	const X0 = 52;
	const X1 = 388; // timeline
	const BAR0 = 410;
	const BAR1 = 442; // undated bar
	const SX0 = 534;
	const SX1 = 738; // sankey
	const START = 1630;
	const END = 2025;

	const catLabel = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.label]));
	const ownerLabel = Object.fromEntries(OWNERS.map((o) => [o.key, o.label]));

	function build(spaces) {
		const feats = spaces.features.map((f) => f.properties);
		const keys = OWNERS.map((o) => o.key);
		const dated = feats.filter((d) => d.year != null);
		const undated = feats.filter((d) => d.year == null);

		// cumulative acres by owner for every year (spaces counted from their acquisition year)
		const rows = d3.range(START, END + 1).map((year) => ({ year, ...Object.fromEntries(keys.map((k) => [k, 0])) }));
		for (const d of dated)
			for (let j = Math.max(0, d.year - START); j < rows.length; j++) rows[j][d.owner] += d.area_acres;
		const series = d3.stack().keys(keys)(rows);

		const sum = (arr, k) => d3.sum(arr.filter((d) => d.owner === k), (d) => d.area_acres);
		const undatedBy = Object.fromEntries(keys.map((k) => [k, sum(undated, k)]));
		const datedTotal = d3.sum(dated, (d) => d.area_acres);
		const undatedTotal = d3.sum(undated, (d) => d.area_acres);

		const x = d3.scaleLinear().domain([START, END]).range([X0, X1]);
		const y = d3.scaleLinear().domain([0, Math.max(datedTotal, undatedTotal)]).nice().range([BOT, TOP]);

		const area = d3.area().x((d) => x(d.data.year)).y0((d) => y(d[0])).y1((d) => y(d[1])).curve(d3.curveStepAfter);
		const layers = series.map((s) => ({ key: s.key, d: area(s) }));

		let acc = 0;
		const undatedSegs = keys.map((k) => {
			const seg = { key: k, y0: y(acc), y1: y(acc + undatedBy[k]), acres: undatedBy[k] };
			acc += undatedBy[k];
			return seg;
		});

		// Sankey: owner -> type, all spaces, acres
		const cats = CATEGORIES.map((c) => c.key);
		const catTotal = Object.fromEntries(cats.map((c) => [c, d3.sum(feats.filter((d) => d.category === c), (d) => d.area_acres)]));
		const catOrder = cats.slice().sort((a, b) => catTotal[b] - catTotal[a]);
		const nodes = [
			...keys.map((k, i) => ({ name: k, kind: 'owner', order: keys.length - 1 - i })),
			...catOrder.map((c, i) => ({ name: c, kind: 'cat', order: i }))
		];
		const links = [];
		for (const k of keys)
			for (const c of cats) {
				const sub = feats.filter((d) => d.owner === k && d.category === c);
				if (sub.length) links.push({ source: keys.indexOf(k), target: keys.length + catOrder.indexOf(c), value: d3.sum(sub, (d) => d.area_acres), n: sub.length });
			}
		const graph = sankey()
			.nodeWidth(12)
			.nodePadding(15)
			.extent([[SX0, TOP], [SX1, BOT]])
			.nodeAlign((n) => (n.kind === 'owner' ? 0 : 1))
			.nodeSort((a, b) => a.order - b.order)({ nodes, links });

		const ownerNodes = new Map(graph.nodes.filter((n) => n.kind === 'owner').map((n) => [n.name, n]));
		const catNodes = new Map(graph.nodes.filter((n) => n.kind === 'cat').map((n) => [n.name, n]));
		const link = sankeyLinkHorizontal();
		return {
			rows,
			x,
			y,
			layers,
			undatedSegs,
			datedTotal,
			undatedTotal,
			nDated: dated.length,
			nUndated: undated.length,
			total: feats.length,
			totalAcres: datedTotal + undatedTotal,
			byId: new Map(feats.map((d) => [d.id, d])),
			graph,
			ownerNodes,
			catNodes,
			links: graph.links.map((l) => ({ ...l, path: link(l), owner: l.source.name, category: l.target.name })),
			yTicks: y.ticks(5),
			xTicks: [1630, 1730, 1830, 1930, 2025]
		};
	}
	const model = $derived(build(spaces));

	// ---- emphasis: from the dot plot hover (owner + type) or from hovering here ----
	let local = $state(null); // { owner?, category? }
	const hovered = $derived(hoverId ? model.byId.get(hoverId) : null);
	const emph = $derived(hovered ? { owner: hovered.owner, category: hovered.category } : local);
	const anyFocus = $derived(!!(emph || filter.owner || filter.category));

	function ownerOn(k) {
		if (emph?.owner) return emph.owner === k;
		if (filter.owner) return filter.owner === k;
		return true;
	}
	function catOn(c) {
		if (emph?.category) return emph.category === c;
		if (filter.category) return filter.category === c;
		return true;
	}
	const linkOn = (l) => ownerOn(l.owner) && catOn(l.category);

	function toggleOwner(k) {
		onfilter({ ...filter, owner: filter.owner === k ? null : k });
	}
	function toggleCat(c) {
		onfilter({ ...filter, category: filter.category === c ? null : c });
	}
	function toggleLink(l) {
		const same = filter.owner === l.owner && filter.category === l.category;
		onfilter(same ? { owner: null, category: null } : { owner: l.owner, category: l.category });
	}
	const key = (fn) => (e) => {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			fn();
		}
	};

	// ---- tooltip + crosshair ----
	let wrap = $state();
	let svg = $state();
	let tt = $state(null);
	let crossYear = $state(null);

	function place(e, content) {
		const w = wrap.getBoundingClientRect();
		const x = e.clientX - w.left;
		tt = { left: x, top: e.clientY - w.top, flip: x > w.width - 260, ...content };
	}
	function svgPoint(e) {
		const r = svg.getBoundingClientRect();
		return [((e.clientX - r.left) * W) / r.width, ((e.clientY - r.top) * H) / r.height];
	}
	function onPlotMove(e) {
		const [px] = svgPoint(e);
		const yr = Math.round(model.x.invert(px));
		if (yr < START || yr > END) {
			crossYear = null;
			return;
		}
		crossYear = yr;
		const row = model.rows[yr - START];
		const rowsOut = OWNERS.filter((o) => row[o.key] > 0).map((o) => ({
			color: o.css,
			label: o.label,
			value: `${fmtInt(row[o.key])} ac`,
			bold: local?.owner === o.key
		}));
		const total = d3.sum(OWNERS, (o) => row[o.key]);
		place(e, { title: `Acquired by ${yr}`, rows: [...rowsOut, { label: 'Total', value: `${fmtInt(total)} ac`, bold: true }] });
	}
	function leavePlot() {
		crossYear = null;
		tt = null;
		local = null;
	}
	function tipNode(e, n) {
		const nSpaces = n.sourceLinks?.length ? d3.sum(n.sourceLinks, (l) => l.n) : d3.sum(n.targetLinks, (l) => l.n);
		place(e, {
			title: n.kind === 'owner' ? ownerLabel[n.name] : catLabel[n.name],
			rows: [
				{ label: 'Area', value: `${fmtInt(n.value)} ac (${((100 * n.value) / model.totalAcres).toFixed(0)}%)` },
				{ label: 'Spaces', value: String(nSpaces) }
			]
		});
	}
	function tipLink(e, l) {
		place(e, {
			title: `${ownerLabel[l.owner]} → ${catLabel[l.category]}`,
			rows: [
				{ label: 'Area', value: `${fmtInt(l.value)} ac` },
				{ label: 'Spaces', value: String(l.n) }
			]
		});
	}
	function tipUndated(e, s) {
		place(e, {
			title: `${ownerLabel[s.key]} · no year recorded`,
			rows: [{ label: 'Area', value: `${fmtInt(s.acres)} ac` }]
		});
	}

	const yearX = $derived(hovered?.year != null ? model.x(hovered.year) : null);
	const hovUndated = $derived(hovered && hovered.year == null ? model.undatedSegs.find((s) => s.key === hovered.owner) : null);
</script>

<div class="wrap" bind:this={wrap}>
	<ul class="how" aria-label="How to use the ownership chart">
		<li><b>Click</b> an owner (legend, layer, bar or left node) or a type (right node) to filter the dot plot; click again to clear. Click a flow to choose both.</li>
		<li><b>Hover a dot</b> in the dot plot to light up that space’s owner, type and acquisition year here.</li>
		<li>Hover the layers for the cumulative area in any year. Hatched = area with no acquisition year on record.</li>
	</ul>

	<div class="owners" role="group" aria-label="Filter by owner">
		<span class="lgt">Owner</span>
		{#each OWNERS as o (o.key)}
			<button
				class="chip"
				class:on={filter.owner === o.key}
				class:dim={filter.owner && filter.owner !== o.key}
				aria-pressed={filter.owner === o.key}
				onclick={() => toggleOwner(o.key)}
			>
				<span class="sw" style:background={o.css}></span>{o.label}
			</button>
		{/each}
		{#if filter.owner || filter.category}
			<button class="chip clear" onclick={() => onfilter({ owner: null, category: null })}>Clear filter</button>
		{/if}
	</div>

	<p class="status" aria-live="polite">
		{#if hovered}
			<strong>{hovered.name}</strong> · {hovered.city} · {ownerLabel[hovered.owner]} · {hovered.category} ·
			{hovered.year != null ? `acquired ${hovered.year}` : 'no acquisition year on record'}
		{:else}
			{fmtInt(model.nDated)} of {model.total} spaces ({fmtInt(model.datedTotal)} of {fmtInt(model.totalAcres)} acres) have a recorded
			acquisition year, all in Boston.
		{/if}
	</p>

	<svg
		bind:this={svg}
		viewBox="0 0 {W} {H}"
		role="img"
		aria-label="Stacked area chart of the area of public space acquired over time by owner, a bar of area with no recorded year, and a flow diagram from owner to type of space."
	>
		<defs>
			<pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
				<rect width="6" height="6" fill="none" />
				<line x1="0" y1="0" x2="0" y2="6" stroke="var(--surface)" stroke-width="2.4" />
			</pattern>
		</defs>

		<!-- panel titles -->
		<text class="panel" x={X0} y="20">Area acquired over time</text>
		<text class="panel-sub" x={X0} y="35">Cumulative acres, by owner · Boston</text>
		<text class="panel" x={BAR0 - 4} y="20">No year</text>
		<text class="panel-sub" x={BAR0 - 4} y="35">recorded</text>
		<text class="panel" x={SX0 - 40} y="20">Owner → type of space</text>
		<text class="panel-sub" x={SX0 - 40} y="35">All {model.total} spaces · acres</text>

		<!-- axes -->
		{#each model.yTicks as t (t)}
			<line class="grid" x1={X0} x2={BAR1} y1={model.y(t)} y2={model.y(t)} />
			<text class="tick" x={X0 - 6} y={model.y(t) + 3.5} text-anchor="end">{fmtInt(t)}</text>
		{/each}
		<text class="tick unit" x={X0 - 6} y={TOP - 10} text-anchor="end">acres</text>
		{#each model.xTicks as t (t)}
			<line class="tick-mark" x1={model.x(t)} x2={model.x(t)} y1={BOT} y2={BOT + 4} />
			<text class="tick" x={model.x(t)} y={BOT + 17} text-anchor="middle">{t}</text>
		{/each}
		<line class="base" x1={X0} x2={BAR1} y1={BOT} y2={BOT} />

		<!-- timeline: stacked areas -->
		<g role="presentation" onpointermove={onPlotMove} onpointerleave={leavePlot}>
			<rect class="catch" x={X0} y={TOP} width={X1 - X0} height={BOT - TOP} />
			{#each model.layers as l (l.key)}
				<path
					class="layer"
					class:dim={!ownerOn(l.key)}
					class:sel={filter.owner === l.key}
					d={l.d}
					style:--c={ownerCss[l.key]}
					role="button"
					tabindex="0"
					aria-pressed={filter.owner === l.key}
					aria-label="{ownerLabel[l.key]}: filter by this owner"
					onpointerenter={() => (local = { owner: l.key })}
					onclick={() => toggleOwner(l.key)}
					onkeydown={key(() => toggleOwner(l.key))}
				/>
			{/each}
			{#if crossYear != null}
				<line class="cross" x1={model.x(crossYear)} x2={model.x(crossYear)} y1={TOP} y2={BOT} />
			{/if}
		</g>
		{#if yearX != null}
			<line class="mark" x1={yearX} x2={yearX} y1={TOP - 6} y2={BOT} />
			<circle class="mark-dot" cx={yearX} cy={BOT} r="4.5" />
			<text class="mark-label" x={Math.min(yearX, X1 - 40)} y={TOP - 10} text-anchor="middle">{hovered.year}</text>
		{/if}

		<!-- undated bar -->
		{#each model.undatedSegs as s (s.key)}
			{#if s.acres > 0}
				<g
					class="seg"
					class:dim={!ownerOn(s.key)}
					role="button"
					tabindex="0"
					aria-pressed={filter.owner === s.key}
					aria-label="{ownerLabel[s.key]}, no year recorded: filter by this owner"
					onpointerenter={(e) => {
						local = { owner: s.key };
						tipUndated(e, s);
					}}
					onpointermove={(e) => tipUndated(e, s)}
					onpointerleave={() => {
						local = null;
						tt = null;
					}}
					onclick={() => toggleOwner(s.key)}
					onkeydown={key(() => toggleOwner(s.key))}
				>
					<rect x={BAR0} y={s.y1} width={BAR1 - BAR0} height={Math.max(0.5, s.y0 - s.y1)} style:fill={ownerCss[s.key]} />
					<rect x={BAR0} y={s.y1} width={BAR1 - BAR0} height={Math.max(0.5, s.y0 - s.y1)} fill="url(#hatch)" />
					{#if filter.owner === s.key}
						<rect class="outline" x={BAR0} y={s.y1} width={BAR1 - BAR0} height={Math.max(0.5, s.y0 - s.y1)} />
					{/if}
				</g>
			{/if}
		{/each}
		{#if hovUndated}
			<text class="mark-label" x={BAR0 + 16} y={Math.max(TOP + 8, hovUndated.y1 - 6)} text-anchor="middle">▼ here</text>
		{/if}

		<!-- sankey -->
		<g class="links">
			{#each model.links as l, i (i)}
				<path
					class="flow"
					d={l.path}
					stroke-width={Math.max(1, l.width)}
					style:--c={ownerCss[l.owner]}
					style:opacity={anyFocus ? (linkOn(l) ? 0.62 : 0.07) : 0.34}
					role="button"
					tabindex="0"
					aria-label="{ownerLabel[l.owner]} to {catLabel[l.category]}: filter by both"
					onpointerenter={(e) => {
						local = { owner: l.owner, category: l.category };
						tipLink(e, l);
					}}
					onpointermove={(e) => tipLink(e, l)}
					onpointerleave={() => {
						local = null;
						tt = null;
					}}
					onclick={() => toggleLink(l)}
					onkeydown={key(() => toggleLink(l))}
				/>
			{/each}
		</g>
		{#each model.graph.nodes as n (n.name)}
			{@const on = n.kind === 'owner' ? ownerOn(n.name) : catOn(n.name)}
			{@const sel = n.kind === 'owner' ? filter.owner === n.name : filter.category === n.name}
			{@const h = Math.max(1.5, n.y1 - n.y0)}
			{@const mid = (n.y0 + n.y1) / 2}
			<g
				class="node"
				class:dim={!on}
				role="button"
				tabindex="0"
				aria-pressed={sel}
				aria-label="{n.kind === 'owner' ? ownerLabel[n.name] : catLabel[n.name]}: filter"
				onpointerenter={(e) => {
					local = n.kind === 'owner' ? { owner: n.name } : { category: n.name };
					tipNode(e, n);
				}}
				onpointermove={(e) => tipNode(e, n)}
				onpointerleave={() => {
					local = null;
					tt = null;
				}}
				onclick={() => (n.kind === 'owner' ? toggleOwner(n.name) : toggleCat(n.name))}
				onkeydown={key(() => (n.kind === 'owner' ? toggleOwner(n.name) : toggleCat(n.name)))}
			>
				<rect class="hit" x={n.kind === 'owner' ? n.x0 - 78 : n.x0} y={mid - Math.max(h, 14) / 2} width={n.kind === 'owner' ? 90 : 132} height={Math.max(h, 14)} />
				<rect class="nrect" class:sel x={n.x0} y={n.y0} width={n.x1 - n.x0} height={h} style:fill={n.kind === 'owner' ? ownerCss[n.name] : 'var(--ink-2)'} />
				{#if n.kind === 'owner'}
					<text class="nlabel" x={n.x0 - 6} y={mid + 3.5} text-anchor="end">{ownerLabel[n.name]}</text>
				{:else}
					<text class="nlabel" x={n.x1 + 6} y={mid + 3.5}>{catLabel[n.name]}</text>
				{/if}
			</g>
		{/each}
	</svg>

	{#if tt}
		<div class="tip" style:left="{tt.flip ? tt.left - 14 : tt.left + 14}px" style:top="{tt.top + 14}px" style:transform={tt.flip ? 'translateX(-100%)' : 'none'} role="tooltip">
			<strong>{tt.title}</strong>
			{#each tt.rows as r (r.label)}
				<div class="row" class:bold={r.bold}>
					{#if r.color}<span class="key" style:background={r.color}></span>{/if}
					<span class="lab">{r.label}</span><span class="val">{r.value}</span>
				</div>
			{/each}
		</div>
	{/if}

	<p class="note">
		Acquisition years exist only for Boston (city records); the other {fmtInt(model.nUndated)} spaces, including most
		state land, appear in the hatched bar. Acres are summed over spaces.
	</p>
</div>

<style>
	.wrap { position: relative; }
	svg { width: 100%; height: auto; display: block; overflow: visible; }
	.how { margin: 0 0 8px; padding: 8px 12px 8px 28px; font-size: 0.78rem; color: var(--ink-2); background: var(--surface-2); border-radius: 8px; }
	.how li + li { margin-top: 3px; }
	.owners { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; margin-bottom: 6px; font-size: 0.8rem; }
	.lgt { font-weight: 700; color: var(--ink); margin-right: 2px; }
	.chip {
		display: inline-flex; align-items: center; gap: 6px; font: inherit; padding: 3px 10px;
		border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: var(--ink); cursor: pointer;
	}
	.chip.on { background: var(--ink); color: var(--surface); border-color: var(--ink); }
	.chip.dim { color: var(--ink-3); }
	.chip.clear { color: var(--ink-2); border-style: dashed; }
	.sw { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
	.status { margin: 0 0 4px; font-size: 0.85rem; color: var(--ink-2); min-height: 2.6em; }
	.panel { fill: var(--ink); font-family: var(--font-title); font-weight: 700; font-size: 14px; }
	.panel-sub { fill: var(--ink-3); font-size: 11px; }
	.grid { stroke: var(--line); stroke-width: 1; }
	.base { stroke: var(--ink-3); stroke-width: 1; }
	.tick { fill: var(--ink-3); font-size: 10.5px; }
	.tick.unit { font-size: 10px; }
	.tick-mark { stroke: var(--ink-3); }
	.catch { fill: transparent; }
	.layer { fill: var(--c); stroke: var(--surface); stroke-width: 1.2; cursor: pointer; transition: opacity 0.12s; }
	.layer.dim { opacity: 0.2; }
	.layer.sel { stroke: var(--ink); stroke-width: 1.8; }
	.layer:focus-visible, .flow:focus-visible { outline: 2px solid var(--ink); }
	.seg:focus-visible, .node:focus-visible { outline: none; }
	.node:focus-visible .nrect, .seg:focus-visible rect:first-child { stroke: var(--ink); stroke-width: 2; }
	.cross { stroke: var(--ink); stroke-width: 1; stroke-dasharray: 3 3; pointer-events: none; }
	.mark { stroke: var(--ink); stroke-width: 1.5; pointer-events: none; }
	.mark-dot { fill: var(--surface); stroke: var(--ink); stroke-width: 2; pointer-events: none; }
	.mark-label { fill: var(--ink); font-size: 11px; font-weight: 700; paint-order: stroke; stroke: var(--surface); stroke-width: 3px; pointer-events: none; }
	.seg { cursor: pointer; transition: opacity 0.12s; }
	.seg.dim { opacity: 0.2; }
	.outline { fill: none; stroke: var(--ink); stroke-width: 1.8; }
	.flow { fill: none; stroke: var(--c); cursor: pointer; transition: opacity 0.12s; }
	.node { cursor: pointer; transition: opacity 0.12s; }
	.node.dim { opacity: 0.3; }
	.hit { fill: transparent; }
	.nrect.sel { stroke: var(--ink); stroke-width: 2; }
	.nlabel { fill: var(--ink); font-size: 11.5px; }
	.tip {
		position: absolute; pointer-events: none; z-index: 3; width: max-content; max-width: 260px; padding: 8px 10px;
		background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 8px;
		box-shadow: 0 4px 14px rgb(0 0 0 / 0.15); font-size: 0.8rem; line-height: 1.35;
	}
	.row { display: flex; align-items: center; gap: 6px; }
	.row .lab { color: var(--ink-2); flex: 1; }
	.row .val { font-variant-numeric: tabular-nums; }
	.row.bold .lab, .row.bold .val { color: var(--ink); font-weight: 700; }
	.key { width: 10px; height: 3px; border-radius: 2px; display: inline-block; }
	.note { margin: 8px 0 0; font-size: 0.75rem; color: var(--ink-3); }
</style>
