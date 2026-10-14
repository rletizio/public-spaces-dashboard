import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// Static build for GitHub Pages. BASE_PATH is set by the deploy workflow (e.g. /public-spaces-dashboard).
			paths: { base: process.env.BASE_PATH ?? '' },
			adapter: adapter({ fallback: '404.html' })
		})
	]
});
