// Three color groups: the first three validated slots of the reference palette (all-pairs safe).
// The five data categories stay available in tooltips; color only separates these groups.
export const GROUPS = [
	{ key: 'green', label: 'Parks, parkways & gardens', css: 'var(--c-green)' },
	{ key: 'plaza', label: 'Squares, plazas & malls', css: 'var(--c-plaza)' },
	{ key: 'play', label: 'Playgrounds & athletic fields', css: 'var(--c-play)' }
];

export function groupOf(category) {
	if (category === 'Square, Plaza & Mall') return 'plaza';
	if (category === 'Playground & Athletic Field') return 'play';
	return 'green';
}

export const groupCss = Object.fromEntries(GROUPS.map((g) => [g.key, g.css]));
