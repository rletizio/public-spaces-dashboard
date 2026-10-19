<script>
	import * as d3 from 'd3';
	import { fmtInt, fmtAcres } from './format.js';

	let { grid, boundaries, water, sizeMode = 'area', shadeMode = 'public', cityFilter = 'all', pinned = $bindable(null), hovered = $bindable(null) } = $props();

	const W = 760;
	const CELL_M2 = 250000; // a full 500 m x 500 m cell
	const ACRES = 4046.8564;
	// five classes of % green, light -> dark (colors are CSS tokens so dark mode gets its own steps)
	const CLASSES = [
		{ lo: 0, hi: 20, label: '0–20%' },
		{ lo: 20, hi: 40, label: '20–40%' },
		{ lo: 40, hi: 60, label: '40–60%' },
		{ lo: 60, hi: 80, label: '60–80%' },
		{ lo: 80, hi: 100.01, label: '80–100%' }
	];
	const classOf = (p) => (p == null ? -1 : Math.min(4, Math.floor(p / 20)));

	function build(grid, boundaries, water) {
		const proj = d3.geoMercator().fitWidth(W, grid);
		const path = d3.geoPath(proj);
		const [[, y0], [, y1]] = path.bounds(grid);
		const H = Math.ceil(y1 + 6);
		const cells = grid.features.map((f) => {
			const [[bx0, by0], [bx1, by1]] = path.bounds(f);
			const [cx, cy] = proj(d3.geoCentroid(f));
			return { id: f.properties.id, p: f.properties, d: path(f), cx, cy, side: (bx1 - bx0 + by1 - by0) / 2 };
		});
		const side = d3.median(cells, (c) => c.side);
		return { H, y0, cells, side, rMax: side * 0.5 * 0.94, boundaryD: path(boundaries), waterD: path(water), byId: new Map(cells.map((c) => [c.id, c])) };
	}
	const model = $derived(build(grid, boundaries, water));

	const radius = (p) => {
		const v = sizeMode === 'area' ? p.pub_m2 / CELL_M2 : p.pub_share / 100;
		return p.pub_m2 > 0 ? Math.max(1.6, model.rMax * Math.sqrt(Math.min(1, v))) : 0;
	};
	const greenPct = (p) => (shadeMode === 'public' ? p.pub_green_pct : p.green_pct);
	const inCity = (p) => cityFilter === 'all' || p.city === cityFilter;

	let focusClass = $state(null); // legend class highlighted by click
	const dim = (p) => !inCity(p) || (focusClass != null && classOf(greenPct(p)) !== focusClass);

	const circles = $derived(model.cells.filter((c) => c.p.pub_m2 > 0));
	const active = $derived((pinned ?? hovered) != null ? model.byId.get(pinned ?? hovered) : null);

	let tip = $state(null);
	let box;
	function move(e, c) {
		const r = box.getBoundingClientRect();
		tip = { x: e.clientX - r.left, y: e.clientY - r.top, flip: e.clientX - r.left > r.width - 230, c };
	}
	function toggle(id) {
		pinned = pinned === id ? null : id;
	}

	// counts for the legend (cells with public space in the selected city)
	const counts = $derived.by(() => {
		const k = Array(5).fill(0);
		let none = 0;
		for (const c of circles) {
			if (!inCity(c.p)) continue;
			const i = classOf(greenPct(c.p));
			if (i < 0) none++;
			else k[i]++;
		}
		return { k, none };
	});
	const sizeKeys = $derived(
		sizeMode === 'area'
			? [{ v: 0.02, t: `${fmtInt((0.02 * CELL_M2) / ACRES)} ac` }, { v: 0.2, t: `${fmtInt((0.2 * CELL_M2) / ACRES)} ac` }, { v: 1, t: `${fmtInt(CELL_M2 / ACRES)} ac` }]
			: [{ v: 0.02, t: '2%' }, { v: 0.2, t: '20%' }, { v: 1, t: '100%' }]
	);
</script>

<div class="wrap" bind:this={box}>
	<svg viewBox="0 0 {W} {model.H}" role="img" aria-label="Grid of 500 m cells over Boston, Cambridge and Somerville. Each circle's size shows how much of the cell is public space and its shade shows how green that space is.">
		<path d={model.waterD} class="water" />
		<path d={model.boundaryD} class="boundary" />
		<g class="cells">
			{#each model.cells as c (c.id)}
				<path d={c.d} class="cell" class:faded={!inCity(c.p)} class:on={active?.id === c.id} />
			{/each}
		</g>
		<g>
			{#each circles as c (c.id)}
				{@const k = classOf(greenPct(c.p))}
				<circle
					cx={c.cx}
					cy={c.cy}
					r={radius(c.p)}
					class="dot"
					class:nodata={k < 0}
					class:faded={dim(c.p)}
					class:pin={pinned === c.id}
					style:fill={k < 0 ? 'none' : `var(--seq-${k + 1})`}
				/>
			{/each}
		</g>
		<!-- transparent hit squares: the whole cell reacts, not just a tiny dot -->
		<g>
			{#each model.cells as c (c.id)}
				<path
					d={c.d}
					class="hit"
					role="button"
					tabindex="-1"
					aria-label="Cell {c.p.row}-{c.p.col}"
					onpointerenter={(e) => { hovered = c.id; move(e, c); }}
					onpointermove={(e) => move(e, c)}
					onpointerleave={() => { hovered = null; tip = null; }}
					onclick={() => toggle(c.id)}
					onkeydown={(e) => e.key === 'Enter' && toggle(c.id)}
				/>
			{/each}
		</g>
		{#if active}
			<path d={active.d} class="ring" class:pinned={pinned === active.id} />
		{/if}
	</svg>

	{#if tip}
		{@const p = tip.c.p}
		<div class="tip" style:left="{tip.flip ? tip.x - 14 : tip.x + 14}px" style:top="{tip.y + 14}px" style:transform={tip.flip ? 'translateX(-100%)' : 'none'} role="tooltip">
			<strong>{p.city}</strong> · cell {p.row}-{p.col}
			{#if p.pub_m2 > 0}
				<div>{fmtAcres(p.pub_m2 / ACRES)} public space ({Math.round(p.pub_share)}% of the cell)</div>
				<div>{greenPct(p) == null ? 'No greenery data' : `${Math.round(greenPct(p))}% green`}{shadeMode === 'all' ? ' (all land in the cell)' : ' (of the public space)'}</div>
			{:else}
				<div>No public space in this cell</div>
			{/if}
		</div>
	{/if}

	<div class="legend">
		<div class="lg">
			<div class="lgt">Shade · % green {shadeMode === 'public' ? 'of the public space' : 'of all land in the cell'}</div>
			<div class="ramp">
				{#each CLASSES as c, i (c.label)}
					<button class="sw" class:sel={focusClass === i} class:off={focusClass != null && focusClass !== i} onclick={() => (focusClass = focusClass === i ? null : i)} title="Highlight cells in this class" aria-pressed={focusClass === i}>
						<span class="chip" style:background="var(--seq-{i + 1})"></span>{c.label}<small>{counts.k[i]}</small>
					</button>
				{/each}
				<span class="sw nodata-sw"><span class="chip hollow"></span>No data<small>{counts.none}</small></span>
			</div>
			<div class="note">Counts are cells with public space. Click a class to highlight it.</div>
		</div>
		<div class="lg">
			<div class="lgt">Size · {sizeMode === 'area' ? 'public space in the cell' : 'share of the cell that is public space'}</div>
			<svg width="150" height="42" aria-hidden="true">
				{#each sizeKeys as s, i (s.t)}
					{@const r = Math.max(1.6, model.rMax * Math.sqrt(s.v))}
					<circle cx={20 + i * 50} cy="18" r={Math.min(r, 17)} class="size" />
					<text x={20 + i * 50} y="40" text-anchor="middle">{s.t}</text>
				{/each}
			</svg>
			<div class="note">No circle = no public space in that 500 m cell.</div>
		</div>
	</div>
</div>

<style>
	.wrap { position: relative; }
	svg { width: 100%; height: auto; display: block; }
	.water { fill: var(--water); }
	.boundary { fill: none; stroke: var(--boundary); stroke-width: 0.9; stroke-dasharray: 3 2; }
	.cell { fill: none; stroke: var(--line); stroke-width: 0.6; }
	.cell.faded { opacity: 0.3; }
	.dot { stroke: var(--ink-3); stroke-opacity: 0.55; stroke-width: 0.7; transition: opacity 0.15s; }
	.dot.nodata { stroke-opacity: 1; stroke-width: 1.2; stroke-dasharray: 2.5 2; }
	.dot.faded { opacity: 0.1; }
	.dot.pin { stroke: var(--ink); stroke-width: 1.6; }
	.hit { fill: transparent; stroke: none; cursor: pointer; outline: none; }
	.ring { fill: none; stroke: var(--ink-2); stroke-width: 1.4; pointer-events: none; }
	.ring.pinned { stroke: var(--ink); stroke-width: 2.2; }
	.tip { position: absolute; z-index: 5; pointer-events: none; max-width: 260px; padding: 7px 10px; font-size: 0.78rem; line-height: 1.35; background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 4px 14px rgb(0 0 0 / 0.16); }
	.legend { display: flex; flex-wrap: wrap; gap: 14px 36px; margin-top: 10px; font-size: 0.78rem; color: var(--ink-2); }
	.lgt { font-weight: 700; color: var(--ink); margin-bottom: 4px; font-size: 0.78rem; }
	.ramp { display: flex; flex-wrap: wrap; gap: 4px 6px; }
	.sw { display: inline-flex; align-items: center; gap: 5px; padding: 3px 7px 3px 4px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: var(--ink-2); font: inherit; font-size: 0.74rem; cursor: pointer; }
	.sw small { color: var(--ink-3); font-size: 0.68rem; }
	.sw.sel { border-color: var(--ink); color: var(--ink); }
	.sw.off { opacity: 0.5; }
	.nodata-sw { cursor: default; }
	.chip { width: 13px; height: 13px; border-radius: 50%; box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.12); }
	.chip.hollow { box-shadow: none; border: 1.2px dashed var(--ink-3); background: none; }
	.note { margin-top: 4px; color: var(--ink-3); font-size: 0.7rem; }
	.size { fill: var(--ink-3); fill-opacity: 0.35; stroke: var(--ink-3); }
	text { fill: var(--ink-2); font-size: 10.5px; }
</style>
