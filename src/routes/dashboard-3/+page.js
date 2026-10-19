import { asset } from '$app/paths';

export async function load({ fetch }) {
	const get = (name) => fetch(asset(`data/${name}.geojson`)).then((r) => r.json());
	const [grid, boundaries, water] = await Promise.all([get('grid'), get('boundaries'), get('water')]);
	return { grid, boundaries, water };
}
