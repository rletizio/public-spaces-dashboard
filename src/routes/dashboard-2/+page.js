import { asset } from '$app/paths';

export async function load({ fetch }) {
	const spaces = await fetch(asset('data/spaces.geojson')).then((r) => r.json());
	return { spaces };
}
