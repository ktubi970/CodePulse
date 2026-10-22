Fix `window(values, start, width)` in `src/window.py`.
It currently includes one extra element at the end of the window. It must return exactly `width` elements starting at index `start`.
