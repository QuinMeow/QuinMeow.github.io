interface PointerLightEnvironment {
	view: Window;
	doc: Document;
}

export function mountPointerLight(
	target: HTMLElement,
	{ view, doc }: PointerLightEnvironment = { view: window, doc: document },
): () => void {
	const finePointer = view.matchMedia("(hover: hover) and (pointer: fine)");
	const reducedMotion = view.matchMedia("(prefers-reduced-motion: reduce)");
	let frame: number | undefined;
	let x = 0;
	let y = 0;
	let pointerInside = false;
	let disposed = false;

	function allowed(): boolean {
		return !disposed && finePointer.matches && !reducedMotion.matches && !doc.hidden && doc.hasFocus();
	}

	function hide(): void {
		pointerInside = false;
		target.dataset.active = "false";
		if (frame !== undefined) view.cancelAnimationFrame(frame);
		frame = undefined;
	}

	function render(): void {
		frame = undefined;
		if (!allowed() || !pointerInside) {
			hide();
			return;
		}
		target.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, -50%)`;
		target.dataset.active = "true";
	}

	function onPointerMove(event: PointerEvent): void {
		if (!allowed() || event.pointerType !== "mouse") {
			hide();
			return;
		}
		x = event.clientX;
		y = event.clientY;
		pointerInside = true;
		// Multiple pointer events share one compositor-only update per frame.
		if (frame === undefined) frame = view.requestAnimationFrame(render);
	}

	hide();
	view.addEventListener("pointermove", onPointerMove, { passive: true });
	doc.documentElement.addEventListener("pointerleave", hide);
	view.addEventListener("blur", hide);
	doc.addEventListener("visibilitychange", hide);
	finePointer.addEventListener("change", hide);
	reducedMotion.addEventListener("change", hide);

	return () => {
		disposed = true;
		hide();
		view.removeEventListener("pointermove", onPointerMove);
		doc.documentElement.removeEventListener("pointerleave", hide);
		view.removeEventListener("blur", hide);
		doc.removeEventListener("visibilitychange", hide);
		finePointer.removeEventListener("change", hide);
		reducedMotion.removeEventListener("change", hide);
	};
}
