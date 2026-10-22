<script lang="ts">
import I18nKey from "@i18n/i18nKey";
import { i18n } from "@i18n/translation";
import Icon from "@iconify/svelte";
import { onMount, tick } from "svelte";
import type { SearchResult } from "@/global";
import { chevronRightIcon, searchIcon } from "./local-icons";

type SearchState = "loading" | "ready" | "unavailable" | "development";
let keyword = "";
let result: SearchResult[] = [];
let panelOpen = false;
let isSearching = false;
let searchFailed = false;
let searchState: SearchState = import.meta.env.DEV ? "development" : "loading";
let inputMobile: HTMLInputElement;
let requestVersion = 0;
let requestTimer: ReturnType<typeof setTimeout> | undefined;

async function togglePanel() {
	panelOpen = !panelOpen;
	if (panelOpen) {
		await tick();
		inputMobile?.focus();
	}
}

function search(value: string, state: SearchState) {
	const version = ++requestVersion;
	clearTimeout(requestTimer);
	result = [];
	searchFailed = false;
	isSearching = false;
	const query = value.trim();
	if (!query || state !== "ready") return;
	isSearching = true;
	requestTimer = setTimeout(async () => {
		try {
			const response = await window.pagefind.search(query);
			if (version !== requestVersion) return;
			const matches = await Promise.all(response.results.map((item) => item.data()));
			if (version !== requestVersion) return;
			result = matches;
		} catch {
			if (version === requestVersion) searchFailed = true;
		} finally {
			if (version === requestVersion) isSearching = false;
		}
	}, 150);
}

onMount(() => {
	const ready = () => {
		searchState = typeof window.pagefind?.search === "function" ? "ready" : "unavailable";
	};
	const unavailable = () => { searchState = "unavailable"; };
	const clickOutside = (event: MouseEvent) => {
		if (!(event.target instanceof Node)) return;
		const target = event.target;
		if (["search-panel", "search-bar", "search-switch"].some((id) => document.getElementById(id)?.contains(target))) return;
		panelOpen = false;
	};
	const escape = (event: KeyboardEvent) => {
		if (event.key !== "Escape") return;
		if (document.getElementById("search-panel")?.contains(document.activeElement)) {
			document.getElementById("search-switch")?.focus();
		}
		panelOpen = false;
	};
	document.addEventListener("pagefindready", ready);
	document.addEventListener("pagefindloaderror", unavailable);
	document.addEventListener("click", clickOutside);
	document.addEventListener("keydown", escape);
	if (import.meta.env.PROD) {
		if (document.documentElement.dataset.pagefindState === "error") unavailable();
		else if (typeof window.pagefind?.search === "function") ready();
	}
	const loadTimeout = setTimeout(() => {
		if (searchState === "loading") unavailable();
	}, 8000);
	return () => {
		requestVersion++;
		clearTimeout(requestTimer);
		clearTimeout(loadTimeout);
		document.removeEventListener("pagefindready", ready);
		document.removeEventListener("pagefindloaderror", unavailable);
		document.removeEventListener("click", clickOutside);
		document.removeEventListener("keydown", escape);
	};
});

$: search(keyword, searchState);
</script>

<div id="search-bar" class="hidden lg:flex transition-all items-center h-11 mr-2 rounded-lg bg-black/[0.04] hover:bg-black/[0.06] focus-within:bg-black/[0.06] dark:bg-white/5 dark:hover:bg-white/10 dark:focus-within:bg-white/10">
    <Icon icon={searchIcon} class="absolute text-[1.25rem] pointer-events-none ml-3 transition my-auto text-black/30 dark:text-white/30" />
    <input type="search" aria-label="搜索文章" aria-controls="search-results" placeholder={i18n(I18nKey.search)} bind:value={keyword} on:focus={() => panelOpen = true} on:input={() => panelOpen = true} autocomplete="off"
        class="transition-all pl-10 pr-3 text-sm bg-transparent outline-0 h-full w-40 active:w-60 focus:w-60 text-black/50 dark:text-white/50" />
</div>

<button type="button" on:click={togglePanel} aria-label="打开站内搜索" aria-controls="search-panel" aria-expanded={panelOpen} id="search-switch" class="btn-plain scale-animation lg:!hidden rounded-lg w-11 h-11 active:scale-90">
    <Icon icon={searchIcon} class="text-[1.25rem]" />
</button>

<div id="search-panel" role="search" aria-label="站内搜索" class:float-panel-closed={!panelOpen} class="float-panel search-panel absolute md:w-[30rem] top-20 left-4 md:left-[unset] right-4 shadow-2xl rounded-2xl p-2">
    <div id="search-bar-inside" class="flex relative lg:hidden transition-all items-center h-11 rounded-xl bg-black/[0.04] hover:bg-black/[0.06] focus-within:bg-black/[0.06] dark:bg-white/5 dark:hover:bg-white/10 dark:focus-within:bg-white/10">
        <Icon icon={searchIcon} class="absolute text-[1.25rem] pointer-events-none ml-3 transition my-auto text-black/30 dark:text-white/30" />
        <input type="search" bind:this={inputMobile} aria-label="搜索文章" aria-controls="search-results" placeholder={i18n(I18nKey.search)} bind:value={keyword} autocomplete="off" class="pl-10 pr-3 w-full h-full text-sm bg-transparent outline-0 text-black/50 dark:text-white/50" />
    </div>
    <div id="search-results" aria-busy={isSearching || searchState === "loading"}>
        {#if !keyword.trim()}
            <p role="status" class="px-3 py-4 text-sm text-50">输入关键词，搜索文章内容。</p>
        {:else if searchState === "development"}
            <p role="status" class="px-3 py-4 text-sm text-50">开发模式尚未生成搜索索引。构建网站并启动预览后即可使用全文搜索。</p>
        {:else if searchState === "loading"}
            <p role="status" class="px-3 py-4 text-sm text-50">正在加载搜索索引...</p>
        {:else if searchState === "unavailable" || searchFailed}
            <p role="status" class="px-3 py-4 text-sm text-50">搜索暂时不可用，请稍后刷新页面重试。</p>
        {:else if isSearching}
            <p role="status" class="px-3 py-4 text-sm text-50">正在搜索...</p>
        {:else if result.length === 0}
            <p role="status" class="px-3 py-4 text-sm text-50">未找到相关文章，请尝试其他关键词。</p>
        {:else}
            <p role="status" class="sr-only">找到 {result.length} 篇相关文章。</p>
        {/if}
        {#each result as item}
            <a href={item.url} class="transition first-of-type:mt-2 lg:first-of-type:mt-0 group block rounded-xl text-lg px-3 py-2 hover:bg-[var(--btn-plain-bg-hover)] active:bg-[var(--btn-plain-bg-active)]">
                <div class="transition text-90 inline-flex font-bold group-hover:text-[var(--primary)]">
                    {item.meta.title}<Icon icon={chevronRightIcon} class="transition text-[0.75rem] translate-x-1 my-auto text-[var(--primary)]" />
                </div>
                <div class="transition text-sm text-50">{@html item.excerpt}</div>
            </a>
        {/each}
    </div>
</div>

<style>
    input:focus { outline: 0; }
    .search-panel { max-height: calc(100vh - 100px); overflow-y: auto; }
</style>
