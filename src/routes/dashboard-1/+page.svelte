<script>
	import { resolve } from '$app/paths';
	import SpaceMap from '#lib/SpaceMap.svelte';
	import AccessPlot from '#lib/AccessPlot.svelte';
	import { GROUPS, groupOf } from '#lib/colors.js';

	let { data } = $props();
	const n = $derived(data.spaces.features.length);
	const counts = $derived(
		Object.fromEntries(
			GROUPS.map((g) => [
				g.key,
				data.spaces.features.filter((f) => groupOf(f.properties.category) === g.key).length
			])
		)
	);

	// state shared by both views
	let focusId = $state(null); // space at the center of the map
	let jump = $state({ id: null, n: 0 }); // request: center the map on a space
	let selection = $state.raw(null); // { rect, ids } brushed on the map
	let hidden = $state.raw(new Set()); // category groups switched off

	const pick = (id) => (jump = { id, n: jump.n + 1 });
	const setSelection = (s) => (selection = s);
	function toggle(key) {
		const next = new Set(hidden);
		if (next.has(key)) next.delete(key);
		else next.add(key);
		hidden = next;
	}
</script>

<svelte:head>
	<title>Public Spaces of Boston, Cambridge & Somerville</title>
</svelte:head>

<main>
	<header>
		<a class="back" href={resolve('/')}>← All dashboards</a>
		<h1>Public spaces of Boston, Cambridge &amp; Somerville</h1>
		<p>
			{n} usable public spaces (parks, squares, plazas, playgrounds, community gardens, parkways),
			excluding cemeteries and conservation land. Sources: MassGIS open space, completed with
			municipal data; population from 2020 census blocks.
		</p>
	</header>

	<div class="filters" role="group" aria-label="Filter by type of space">
		<span class="flabel">Show types:</span>
		{#each GROUPS as g (g.key)}
			<button class="chip" class:off={hidden.has(g.key)} aria-pressed={!hidden.has(g.key)} onclick={() => toggle(g.key)}>
				<span class="swatch" style:background={g.css}></span>
				{g.label} <span class="count">{counts[g.key]}</span>
			</button>
		{/each}
		<span class="fhint">Click a type to hide or show it in both views.</span>
	</div>

	<div class="grid">
		<section class="card">
			<h2>Look at one space</h2>
			<p class="lede">
				Pan the map to center any space and see how large it is and how many people live around it,
				compared with every other space.
			</p>
			<SpaceMap
				spaces={data.spaces}
				boundaries={data.boundaries}
				water={data.water}
				bind:focusId
				jumpRequest={jump}
				{selection}
				hiddenGroups={hidden}
				onselect={setSelection}
			/>
		</section>

		<section class="card">
			<h2>Who lives near each space?</h2>
			<p class="lede">
				Each dot is a space, placed by the number of people living within 500 m (straight-line, from
				the space border). Bigger dots are bigger spaces.
			</p>
			<AccessPlot
				spaces={data.spaces}
				highlightId={focusId}
				{selection}
				hiddenGroups={hidden}
				onpick={pick}
			/>
		</section>
	</div>

	<footer>
		Prototype · distances are straight-line, not walking routes · private-owned spaces are those the
		sources flag as publicly accessible · basemap © OpenStreetMap contributors.
	</footer>
</main>

<style>
	main { max-width: 1680px; margin: 0 auto; padding: 24px 24px 40px; }
	header { margin-bottom: 14px; }
	.back { font-size: 0.8rem; color: var(--ink-3); text-decoration: none; }
	.back:hover { color: var(--ink); text-decoration: underline; }
	h1 { font-size: 2rem; }
	header p { margin: 6px 0 0; color: var(--ink-2); max-width: 80ch; }
	.filters { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 10px; margin-bottom: 16px; font-size: 0.85rem; }
	.flabel { font-weight: 700; font-family: var(--font-title); font-size: 1rem; }
	.chip {
		display: inline-flex; align-items: center; gap: 8px; font: inherit; padding: 5px 12px;
		border: 1px solid var(--line); border-radius: 999px; background: var(--surface); color: var(--ink); cursor: pointer;
	}
	.chip.off { color: var(--ink-3); text-decoration: line-through; background: var(--surface-2); }
	.chip.off .swatch { opacity: 0.3; }
	.swatch { width: 11px; height: 11px; border-radius: 50%; display: inline-block; }
	.count { color: var(--ink-3); font-size: 0.78rem; }
	.fhint { color: var(--ink-3); font-size: 0.78rem; }
	.grid { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 24px; align-items: start; }
	.card { border: 1px solid var(--line); border-radius: 12px; padding: 18px; background: var(--surface); }
	h2 { font-size: 1.35rem; }
	.lede { margin: 4px 0 12px; color: var(--ink-2); font-size: 0.9rem; max-width: 66ch; }
	footer { margin-top: 20px; font-size: 0.75rem; color: var(--ink-3); }
	@media (max-width: 1000px) { .grid { grid-template-columns: minmax(0, 1fr); } }
</style>
