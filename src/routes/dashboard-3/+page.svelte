<script>
	import { resolve } from '$app/paths';
	import GreenGrid from '#lib/GreenGrid.svelte';
	import { fmtInt, fmtAcres } from '#lib/format.js';

	let { data } = $props();
	const ACRES = 4046.8564;

	let sizeMode = $state('area'); // 'area' | 'share'
	let shadeMode = $state('public'); // 'public' | 'all'
	let cityFilter = $state('all');
	let pinned = $state(null);
	let hovered = $state(null);

	const cells = $derived(data.grid.features.map((f) => f.properties));
	const byId = $derived(new Map(cells.map((p) => [p.id, p])));
	const shown = $derived(byId.get(pinned ?? hovered) ?? null);
	const greenOf = (p) => (shadeMode === 'public' ? p.pub_green_pct : p.green_pct);

	// headline numbers for the selected city
	const stats = $derived.by(() => {
		const rows = cells.filter((p) => (cityFilter === 'all' || p.city === cityFilter) && p.pub_m2 > 0);
		const area = rows.reduce((s, p) => s + p.pub_m2, 0);
		const withGreen = rows.filter((p) => p.pub_green_pct != null);
		const gArea = withGreen.reduce((s, p) => s + p.pub_m2, 0);
		const green = withGreen.reduce((s, p) => s + (p.pub_m2 * p.pub_green_pct) / 100, 0);
		return {
			n: rows.length,
			area,
			green: gArea ? (100 * green) / gArea : null,
			low: rows.filter((p) => p.pub_green_pct != null && p.pub_green_pct < 20).length
		};
	});
	const top = $derived(
		cells
			.filter((p) => p.pub_m2 > 0 && (cityFilter === 'all' || p.city === cityFilter))
			.sort((a, b) => b.pub_m2 - a.pub_m2)
			.slice(0, 12)
	);

	const instructions = [
		'<b>Hover</b> a square to see its public space and greenery; <b>click</b> to pin it and list the spaces inside.',
		'Circle size = public space in the 500 m × 500 m cell; shade = share of that space covered by greenery.',
		'Click a shade in the legend to highlight those cells; use the controls to change the size and shade measures.'
	];
	const CITIES = [
		['all', 'All'],
		['Boston', 'Boston'],
		['Cambridge', 'Cambridge'],
		['Somerville', 'Somerville']
	];
</script>

<svelte:head>
	<title>How green is public space? · Public Spaces Dashboards</title>
</svelte:head>

<main>
	<header>
		<a class="back" href={resolve('/')}>← All dashboards</a>
		<h1>How much public space is there, and how green is it?</h1>
		<p>
			Boston, Cambridge and Somerville divided into a regular grid of 500 m cells. Each circle shows how much public
			space a cell holds and how green that space is, giving an overview of where public space is dense, sparse, leafy
			or paved.
		</p>
	</header>

	<div class="controls" role="group" aria-label="Controls">
		<div class="ctl">
			<span>City</span>
			<div class="seg">
				{#each CITIES as [k, l] (k)}
					<button class:on={cityFilter === k} onclick={() => (cityFilter = k)} aria-pressed={cityFilter === k}>{l}</button>
				{/each}
			</div>
		</div>
		<div class="ctl">
			<span>Size</span>
			<div class="seg">
				<button class:on={sizeMode === 'area'} onclick={() => (sizeMode = 'area')} aria-pressed={sizeMode === 'area'}>Public space area</button>
				<button class:on={sizeMode === 'share'} onclick={() => (sizeMode = 'share')} aria-pressed={sizeMode === 'share'}>Share of the cell</button>
			</div>
		</div>
		<div class="ctl">
			<span>Shade</span>
			<div class="seg">
				<button class:on={shadeMode === 'public'} onclick={() => (shadeMode = 'public')} aria-pressed={shadeMode === 'public'}>Green in public space</button>
				<button class:on={shadeMode === 'all'} onclick={() => (shadeMode = 'all')} aria-pressed={shadeMode === 'all'}>Green on all land</button>
			</div>
		</div>
	</div>

	<div class="grid">
		<section class="card">
			<div class="kpis">
				<div><b>{fmtInt(stats.n)}</b><span>cells with public space</span></div>
				<div><b>{fmtInt(stats.area / ACRES)} ac</b><span>of public space</span></div>
				<div><b>{stats.green == null ? '–' : `${Math.round(stats.green)}%`}</b><span>of it is green (by area)</span></div>
				<div><b>{stats.low}</b><span>cells under 20% green</span></div>
			</div>
			<GreenGrid grid={data.grid} boundaries={data.boundaries} water={data.water} {sizeMode} {shadeMode} {cityFilter} bind:pinned bind:hovered />
			<ul class="help">
				{#each instructions as t (t)}<li>{@html t}</li>{/each}
			</ul>
		</section>

		<aside class="card side">
			<h2>{shown ? `${shown.city} · cell ${shown.row}-${shown.col}` : 'Cell details'}</h2>
			{#if !shown}
				<p class="lede">Hover or click a square on the map. Its details and the spaces inside it appear here.</p>
			{:else}
				<p class="lede">{pinned != null ? 'Pinned — click the square again to release.' : 'Click to pin this cell.'}</p>
				<dl>
					<div><dt>Public space</dt><dd>{fmtAcres(shown.pub_m2 / ACRES)} <small>({fmtInt(shown.pub_m2)} m²)</small></dd></div>
					<div><dt>Share of the cell</dt><dd>{Math.round(shown.pub_share)}%</dd></div>
					<div><dt>Green, public space</dt><dd>{shown.pub_green_pct == null ? 'no data' : `${Math.round(shown.pub_green_pct)}%`}</dd></div>
					<div><dt>Green, all land</dt><dd>{shown.green_pct == null ? 'no data' : `${Math.round(shown.green_pct)}%`}</dd></div>
					<div><dt>Water</dt><dd>{Math.round(shown.water_pct)}% of the cell</dd></div>
				</dl>
				{#if shown.spaces.length}
					<h3>Spaces in this cell</h3>
					<ul class="spaces">
						{#each shown.spaces as s (s.id)}
							<li>
								<span class="nm">{s.name}</span>
								<span class="mt">{s.category} · {fmtAcres(s.area_m2 / ACRES)} here · {s.green_pct == null ? 'no green data' : `${s.green_pct}% green`}</span>
							</li>
						{/each}
					</ul>
					{#if shown.n_spaces > shown.spaces.length}<p class="more">+ {shown.n_spaces - shown.spaces.length} smaller spaces</p>{/if}
				{:else}
					<p class="lede">No public space in this cell.</p>
				{/if}
			{/if}

			<details class="tbl">
				<summary>Table: largest public-space cells{cityFilter === 'all' ? '' : ` in ${cityFilter}`}</summary>
				<table>
					<thead><tr><th>Cell</th><th>City</th><th class="num">Public space</th><th class="num">% green</th></tr></thead>
					<tbody>
						{#each top as p (p.id)}
							<tr class:sel={pinned === p.id} onclick={() => (pinned = pinned === p.id ? null : p.id)}>
								<td>{p.row}-{p.col}</td>
								<td>{p.city}</td>
								<td class="num">{fmtAcres(p.pub_m2 / ACRES)}</td>
								<td class="num">{greenOf(p) == null ? '–' : `${Math.round(greenOf(p))}%`}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</details>
		</aside>
	</div>

	<footer>
		Prototype · cells are 500 m × 500 m and count only the part inside the three cities · “green” is vegetation and tree
		cover from the land-cover layer, so a park can be under 100% green (courts, paths, plazas) · cells with public space
		but no land-cover data are drawn hollow.
	</footer>
</main>

<style>
	main { max-width: 1680px; margin: 0 auto; padding: 24px 24px 40px; }
	header { margin-bottom: 14px; }
	.back { font-size: 0.8rem; color: var(--ink-3); text-decoration: none; }
	.back:hover { color: var(--ink); text-decoration: underline; }
	h1 { font-size: 2rem; }
	header p { margin: 6px 0 0; color: var(--ink-2); max-width: 80ch; }
	.controls { display: flex; flex-wrap: wrap; gap: 10px 28px; margin: 0 0 14px; }
	.ctl { display: flex; align-items: center; gap: 8px; font-size: 0.8rem; color: var(--ink-2); }
	.ctl > span { font-weight: 700; color: var(--ink); }
	.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
	.seg button { padding: 5px 11px; border: 0; background: var(--surface); color: var(--ink-2); font: inherit; font-size: 0.8rem; cursor: pointer; }
	.seg button + button { border-left: 1px solid var(--line); }
	.seg button.on { background: var(--ink); color: var(--surface); }
	.grid { display: grid; grid-template-columns: minmax(0, 1.9fr) minmax(300px, 1fr); gap: 24px; align-items: start; }
	.card { border: 1px solid var(--line); border-radius: 12px; padding: 18px; background: var(--surface); }
	.kpis { display: flex; flex-wrap: wrap; gap: 8px 28px; margin-bottom: 10px; }
	.kpis div { display: flex; flex-direction: column; }
	.kpis b { font-family: var(--font-title); font-size: 1.5rem; line-height: 1.1; }
	.kpis span { font-size: 0.75rem; color: var(--ink-3); }
	.help { margin: 10px 0 0; padding-left: 18px; font-size: 0.78rem; color: var(--ink-2); }
	h2 { font-size: 1.35rem; }
	h3 { font-size: 1rem; margin-top: 14px; }
	.lede { margin: 4px 0 10px; color: var(--ink-2); font-size: 0.9rem; }
	dl { margin: 0; display: grid; gap: 4px; }
	dl div { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding: 3px 0; font-size: 0.85rem; }
	dt { color: var(--ink-2); }
	dd { margin: 0; font-weight: 600; text-align: right; }
	dd small { font-weight: 400; color: var(--ink-3); }
	.spaces { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 6px; }
	.spaces li { display: flex; flex-direction: column; font-size: 0.84rem; }
	.nm { font-weight: 600; }
	.mt { color: var(--ink-3); font-size: 0.74rem; }
	.more { font-size: 0.78rem; color: var(--ink-3); margin: 6px 0 0; }
	.tbl { margin-top: 16px; font-size: 0.8rem; }
	.tbl summary { cursor: pointer; color: var(--ink-2); font-weight: 600; }
	table { border-collapse: collapse; width: 100%; margin-top: 6px; }
	th, td { padding: 3px 6px; text-align: left; border-bottom: 1px solid var(--line); }
	th { color: var(--ink-3); font-weight: 600; font-size: 0.72rem; }
	.num { text-align: right; font-variant-numeric: tabular-nums; }
	tbody tr { cursor: pointer; }
	tbody tr:hover, tbody tr.sel { background: var(--surface-2); }
	footer { margin-top: 20px; font-size: 0.75rem; color: var(--ink-3); max-width: 120ch; }
	@media (max-width: 1000px) { .grid { grid-template-columns: minmax(0, 1fr); } }
</style>
