<script>
	import * as d3 from 'd3';

	// values: every space's value; value: the focused space's value.
	let { title, values, value, scale = 'linear', ticks, format, valueLabel } = $props();

	const W = 330;
	const H = 82;
	const M = { l: 8, r: 8 };
	const axisY = 54;

	const model = $derived.by(() => {
		const sorted = [...values].sort((a, b) => a - b);
		const lo = sorted[0];
		const hi = sorted[sorted.length - 1];
		const x = (scale === 'log' ? d3.scaleLog() : d3.scaleLinear())
			.domain([lo, hi])
			.range([M.l, W - M.r]);
		const rand = d3.randomLcg(7);
		const dots = values.map((v) => ({ x: x(v), y: 24 + rand() * 20 }));
		return {
			x,
			dots,
			q1: d3.quantileSorted(sorted, 0.25),
			med: d3.quantileSorted(sorted, 0.5),
			q3: d3.quantileSorted(sorted, 0.75),
			lo,
			hi
		};
	});
</script>

<figure class="strip">
	<figcaption>{title}</figcaption>
	<svg viewBox="0 0 {W} {H}" role="img" aria-label="{title}: this space {valueLabel}">
		<line class="axis" x1={M.l} x2={W - M.r} y1={axisY} y2={axisY} />
		<rect
			class="iqr"
			x={model.x(model.q1)}
			width={model.x(model.q3) - model.x(model.q1)}
			y={axisY - 6}
			height="12"
			rx="2"
		/>
		<line class="med" x1={model.x(model.med)} x2={model.x(model.med)} y1={axisY - 6} y2={axisY + 6} />
		{#each model.dots as d, i (i)}
			<circle class="dot" cx={d.x} cy={d.y} r="1.8" />
		{/each}
		{#each ticks as t (t.v)}
			<line class="tick" x1={model.x(t.v)} x2={model.x(t.v)} y1={axisY + 6} y2={axisY + 10} />
			<text class="tick-label" x={model.x(t.v)} y={axisY + 21} text-anchor="middle">{t.label}</text>
		{/each}
		{#if value != null}
			{@const hx = model.x(value)}
			<line class="leader" x1={hx} x2={hx} y1="14" y2={axisY} />
			<circle class="hl" cx={hx} cy="14" r="5" />
		{/if}
	</svg>
	<p class="legend">
		<span class="swatch"></span> Grey box: middle half of all spaces (line = median)
	</p>
</figure>

<style>
	.strip { margin: 0; }
	figcaption { font-size: 0.8rem; font-weight: 600; color: var(--ink-2); margin-bottom: 2px; }
	svg { width: 100%; height: auto; display: block; overflow: visible; }
	.axis { stroke: var(--line); stroke-width: 1; }
	.iqr { fill: var(--surface-2); stroke: var(--line); }
	.med { stroke: var(--ink-3); stroke-width: 1.5; }
	.dot { fill: var(--ink-3); opacity: 0.45; }
	.tick { stroke: var(--ink-3); }
	.tick-label { fill: var(--ink-3); font-size: 9.5px; }
	.leader { stroke: var(--accent); stroke-width: 1.5; }
	.hl { fill: var(--accent); stroke: var(--surface); stroke-width: 2; }
	.legend { margin: 6px 0 0; font-size: 0.7rem; color: var(--ink-3); }
	.swatch {
		display: inline-block; width: 12px; height: 8px; border-radius: 2px;
		background: var(--surface-2); border: 1px solid var(--line); vertical-align: -1px;
	}
</style>
