import { asset } from '$app/paths';

export async function load({ fetch }) {
	const get = (name) => fetch(asset(`data/${name}.geojson`)).then((r) => r.json());
	const [spaces, boundaries, water] = await Promise.all([
		get('spaces'),
		get('boundaries'),
		get('water')
	]);
	return { spaces, boundaries, water };
}
