import { PAGE_SIZE } from './api.js';

/**
 * InfiniteScroll — observes a sentinel element at the bottom of a list
 * and calls fetchFn(offset) to load more items.
 *
 * fetchFn(offset) must return { results: [], total: number|null }
 * renderFn(tracks) must append rendered HTML to the list container
 */
export class InfiniteScroll {
  constructor({ listEl, statusEl, fetchFn, renderFn }) {
    this._list     = listEl;
    this._status   = statusEl;
    this._fetchFn  = fetchFn;
    this._renderFn = renderFn;

    this._offset   = 0;
    this._total    = null;
    this._loading  = false;
    this._done     = false;

    this._sentinel = document.createElement('div');
    this._sentinel.className = 'h-4';
    this._list.after(this._sentinel);

    this._observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting) this._loadMore();
    }, { rootMargin: '200px' });

    this._observer.observe(this._sentinel);
  }

  /** Load the first page immediately */
  async start() {
    await this._loadMore();
  }

  /** Tear down observer (call when view unmounts) */
  destroy() {
    this._observer.disconnect();
    this._sentinel.remove();
  }

  async _loadMore() {
    if (this._loading || this._done) return;
    this._loading = true;
    this._setStatus('loading');

    try {
      const data = await this._fetchFn(this._offset);
      const results = data.results || [];

      if (data.total != null) this._total = data.total;

      if (!results.length) {
        this._done = true;
        this._setStatus('done');
        return;
      }

      this._renderFn(results, this._offset);
      this._offset += results.length;

      if (results.length < PAGE_SIZE) {
        this._done = true;
        this._observer.disconnect();
      }

      this._setStatus('idle');

      // Re-check immediately in case sentinel is still visible after render
      requestAnimationFrame(() => {
        if (!this._done) {
          const rect = this._sentinel.getBoundingClientRect();
          if (rect.top < window.innerHeight + 200) this._loadMore();
        }
      });
    } catch {
      this._setStatus('error');
    } finally {
      this._loading = false;
    }
  }

  _setStatus(state) {
    if (!this._status) return;
    const shown = this._offset;
    const total = this._total;
    const countStr = total != null
      ? `${shown.toLocaleString()} of ${total.toLocaleString()}`
      : `${shown.toLocaleString()}`;

    const states = {
      loading: `<span class="text-white/30">Loading…</span>`,
      idle:    `<span class="text-white/30">Showing ${countStr}</span>`,
      done:    `<span class="text-white/30">${countStr} track${shown !== 1 ? 's' : ''}</span>`,
      error:   `<span class="text-white/40">Failed to load. Scroll up to retry.</span>`,
    };
    this._status.innerHTML = states[state] || '';
  }
}
