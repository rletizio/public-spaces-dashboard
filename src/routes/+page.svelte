<script>
	import { resolve } from '$app/paths';

	// Add new dashboards here: create src/routes/<name>/+page.svelte and list it.
	const dashboards = [
		{
			path: '/dashboard-1',
			title: 'Dashboard 1 · Who lives near each public space?',
			text: 'A map of public spaces linked to a dot plot of the people living within 500 m of each one (Boston, Cambridge and Somerville).'
		}
	];
</script>

<svelte:head>
	<title>Public Spaces Dashboards</title>
</svelte:head>

<main>
	<h1>Public spaces of Boston, Cambridge &amp; Somerville</h1>
	<p class="lede">Interactive dashboards for the CS171 visualization project.</p>
	<ul>
		{#each dashboards as d (d.path)}
			<li>
				<a href={resolve(d.path)}>
					<h2>{d.title}</h2>
					<p>{d.text}</p>
				</a>
			</li>
		{/each}
	</ul>
</main>

<style>
	main { max-width: 760px; margin: 0 auto; padding: 48px 24px; }
	h1 { font-size: 2rem; }
	.lede { color: var(--ink-2); margin: 6px 0 24px; }
	ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 14px; }
	a { display: block; padding: 16px 18px; border: 1px solid var(--line); border-radius: 12px; color: inherit; text-decoration: none; }
	a:hover { border-color: var(--ink-3); background: var(--surface-2); }
	h2 { font-size: 1.2rem; }
	a p { margin: 4px 0 0; color: var(--ink-2); font-size: 0.9rem; }
</style>
