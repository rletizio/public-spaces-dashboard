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

// Ownership classes, in stacking order (bottom -> top). Hues are validated as adjacent pairs.
export const OWNERS = [
	{ key: 'City', label: 'City', css: 'var(--o-city)' },
	{ key: 'State', label: 'State', css: 'var(--o-state)' },
	{ key: 'Private', label: 'Private', css: 'var(--o-private)' },
	{ key: 'Other public', label: 'Other public', css: 'var(--o-other)' },
	{ key: 'Nonprofit / institutional', label: 'Nonprofit', css: 'var(--o-nonprofit)' },
	{ key: 'Unknown', label: 'Unknown', css: 'var(--o-unknown)' }
];
export const ownerCss = Object.fromEntries(OWNERS.map((o) => [o.key, o.css]));

export const CATEGORIES = [
	{ key: 'Park', label: 'Parks' },
	{ key: 'Parkway, Reservation & Waterfront', label: 'Parkways & reservations' },
	{ key: 'Playground & Athletic Field', label: 'Playgrounds & fields' },
	{ key: 'Square, Plaza & Mall', label: 'Squares & plazas' },
	{ key: 'Community Garden', label: 'Gardens' }
];
