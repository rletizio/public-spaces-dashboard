export const SQFT_PER_M2 = 10.7639;

export function fmtArea(m2) {
	const ft = m2 * SQFT_PER_M2;
	if (ft >= 1e6) return `${(ft / 1e6).toFixed(2)}M ft²`;
	if (ft >= 1e3) return `${(ft / 1e3).toFixed(1)}k ft²`;
	return `${Math.round(ft)} ft²`;
}

export function fmtAcres(ac) {
	const v = ac < 0.1 ? ac.toFixed(2) : ac < 10 ? ac.toFixed(1) : Math.round(ac).toLocaleString('en-US');
	return `${v} ac`;
}

export function fmtInt(n) {
	return Math.round(n).toLocaleString('en-US');
}

export function fmtCompact(n) {
	if (n >= 10000) return `${Math.round(n / 1000)}k`;
	if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
	return String(Math.round(n));
}

export function ordinal(n) {
	const s = ['th', 'st', 'nd', 'rd'];
	const v = n % 100;
	return n + (s[(v - 20) % 10] || s[v] || s[0]);
}
