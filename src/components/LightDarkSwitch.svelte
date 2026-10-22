<script lang="ts">
import { AUTO_MODE, DARK_MODE, LIGHT_MODE } from "@constants/constants.ts";
import Icon from "@iconify/svelte";
import { applyThemeToDocument, getStoredTheme, setTheme } from "@utils/setting-utils.ts";
import { onMount } from "svelte";
import type { LIGHT_DARK_MODE } from "@/types/config.ts";
import { autoModeIcon, darkModeIcon, lightModeIcon } from "./local-icons";

let mode: LIGHT_DARK_MODE = $state(AUTO_MODE);
const sequence: LIGHT_DARK_MODE[] = [AUTO_MODE, LIGHT_MODE, DARK_MODE];
const labels = { [AUTO_MODE]: "自动", [LIGHT_MODE]: "浅色", [DARK_MODE]: "深色" };
const nextMode = $derived(sequence[(sequence.indexOf(mode) + 1) % sequence.length]);
const hint = $derived(`当前主题：${labels[mode]}，点击切换为${labels[nextMode]}`);

function cycleTheme() {
	mode = nextMode;
	setTheme(mode);
}
onMount(() => {
	mode = getStoredTheme();
	const preference = window.matchMedia("(prefers-color-scheme: dark)");
	const update = () => applyThemeToDocument(mode);
	preference.addEventListener("change", update);
	return () => preference.removeEventListener("change", update);
});
</script>

<div class="theme-control">
    <button id="scheme-switch" type="button" class="theme-cycle" data-theme={mode} aria-label={hint} title={hint} onclick={cycleTheme}>
        <Icon icon={mode === DARK_MODE ? darkModeIcon : mode === LIGHT_MODE ? lightModeIcon : autoModeIcon} aria-hidden="true" />
        <span class="sr-only" aria-live="polite">{labels[mode]}模式</span>
    </button>
</div>
