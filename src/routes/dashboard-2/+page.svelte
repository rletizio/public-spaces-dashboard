<script>
	import { resolve } from '$app/paths';
	import AccessPlot from '#lib/AccessPlot.svelte';
	import OwnershipTimeline from '#lib/OwnershipTimeline.svelte';

	let { data } = $props();
	const n = $derived(data.spaces.features.length);

	// state shared by both views
	let hoverId = $state(null); // space hovered in the dot plot -> highlighted in the ownership chart
	let filter = $state.raw({ owner: null, category: null }); // chosen in the ownership chart -> filters the dot plot

	const instructions = [
		'<b>Hover</b> a dot for the space’s details; its owner, type and acquisition year light up in the ownership chart on the right.',
		'Dots fade when they do not match the owner or type you <b>clicked</b> in the ownership chart.',
		'Dot color = owner (same colors as the ownership chart); hollow dots are privately owned spaces open to the public.'
	];
</script>

<svelte:head>
	<title>Who owns public space? · Public Spaces Dashboards</title>
</svelte:head>

<main>
	<header>
		<a class="back" href={resolve('/')}>← All dashboards</a>
		<h1>Who owns public space, and who lives near it?</h1>
		<p>
			{n} usable public spaces in Boston, Cambridge and Somerville. Explore who owns each type of space and when
			Boston acquired it, and see how those groups sit in terms of the people living within 500 m.
		</p>
	</header>

	<div class="grid">
		<section class="card">
			<h2>Who lives near each space?</h2>
			<p class="lede">
				Each dot is a space, placed by the number of people living within 500 m (straight-line, from the space
				border). Bigger dots are bigger spaces.
			</p>
			<AccessPlot
				spaces={data.spaces}
				colorMode="owner"
				{filter}
				tipHint=""
				statusHint="Hover a dot for details, or click an owner or type on the right to filter."
				{instructions}
				onhover={(id) => (hoverId = id)}
			/>
		</section>

		<section class="card">
			<h2>Who owns it, and what kind of space is it?</h2>
			<p class="lede">
				Area of public space by owner: acquired over time where a year is on record, and split into types of
				space. Click an owner or a type to filter the dots on the left.
			</p>
			<OwnershipTimeline
				spaces={data.spaces}
				{hoverId}
				{filter}
				onfilter={(f) => (filter = f)}
			/>
		</section>
	</div>

	<footer>
		Prototype · acquisition years come from Boston records only · distances are straight-line, not walking routes ·
		private-owned spaces are those the sources flag as publicly accessible.
	</footer>
</main>

<style>
	main { max-width: 1680px; margin: 0 auto; padding: 24px 24px 40px; }
	header { margin-bottom: 16px; }
	.back { font-size: 0.8rem; color: var(--ink-3); text-decoration: none; }
	.back:hover { color: var(--ink); text-decoration: underline; }
	h1 { font-size: 2rem; }
	header p { margin: 6px 0 0; color: var(--ink-2); max-width: 80ch; }
	.grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 24px; align-items: start; }
	.card { border: 1px solid var(--line); border-radius: 12px; padding: 18px; background: var(--surface); }
	h2 { font-size: 1.35rem; }
	.lede { margin: 4px 0 12px; color: var(--ink-2); font-size: 0.9rem; max-width: 66ch; }
	footer { margin-top: 20px; font-size: 0.75rem; color: var(--ink-3); }
	@media (max-width: 1000px) { .grid { grid-template-columns: minmax(0, 1fr); } }
</style>
