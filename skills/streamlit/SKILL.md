---
name: streamlit
description: >
  Build interactive Streamlit apps for data exploration, visualization dashboards,
  and educational tools. Use this skill whenever the user asks to create a Streamlit app,
  an interactive visualization, a data explorer, a dashboard, or any tool where they want
  sliders/dropdowns/controls alongside charts or plots. Also trigger when the user says
  things like "make it interactive", "let me play with the parameters", "build a dashboard",
  "visualize this data", or wants to explore a dataset interactively — even if they don't
  explicitly mention Streamlit. If the user already has a Streamlit project (look for
  streamlit in pyproject.toml or requirements.txt, or existing .py files that import
  streamlit), default to this skill for new visualization work in that project.
---

# Streamlit App Builder

## What this skill is for

Streamlit turns Python scripts into interactive web apps with zero frontend code. It's the
right tool when the user wants to explore data with controls (sliders, dropdowns, toggles),
build a dashboard that updates live, or create an educational visualization where parameters
can be tweaked. It's not the right tool for static one-off charts (use matplotlib directly)
or production web apps (use React/Flask).

## Before writing any code

1. **Check for an existing project.** Look for `pyproject.toml`, `requirements.txt`, or
   existing `.py` files. If there's already a Streamlit app, build on it rather than
   starting from scratch.

2. **Check for a data source.** If the user has CSV, YAML, JSON, or database files they
   want to visualize, read them first so you understand the schema. The app should load
   real data, not placeholders.

3. **Add streamlit to the project's dependencies.** If there's a `pyproject.toml`, add
   `streamlit` to the dependencies list. If there's a `requirements.txt`, add it there.
   Also add any plotting libraries you'll need (matplotlib, plotly, altair, etc.).

## App structure

### Single-file apps (the default)

Most Streamlit apps should be a single `.py` file. This keeps things simple and
self-contained. Only split into multiple files if the app genuinely has multiple
distinct pages (not just multiple charts on one page).

### Standard layout

```python
"""
Short description of what this app does.

Run with:  streamlit run app_name.py
"""

import streamlit as st
# other imports

# 1. Page config (must be first st call)
st.set_page_config(page_title="...", layout="wide")  # or layout="centered"

# 2. Data loading (cached)
@st.cache_data
def load_data():
    ...

# 3. Sidebar controls
st.sidebar.title("Controls")
param = st.sidebar.slider("Parameter", min, max, default)

# 4. Main content
st.title("App Title")
# tabs, columns, charts, etc.
```

### Key principles

**Cache data loading.** Always use `@st.cache_data` for loading files, parsing configs,
or any computation that doesn't need to re-run on every interaction. Streamlit reruns
the entire script on every widget change — without caching, large datasets reload on
every slider tweak.

**Sidebar for controls, main area for content.** Put sliders, dropdowns, and selectors
in the sidebar. Put charts, tables, and explanatory text in the main area. This keeps
the layout clean and gives the charts maximum space.

**Use tabs for multiple views.** When the app has distinct sections (e.g., different
ways to look at the same data), use `st.tabs()` rather than stuffing everything into
one long scrolling page.

**Real data, not lorem ipsum.** Load actual data files from the project. If the data
comes from a config file (YAML, JSON), parse it and use it. The whole point of Streamlit
is making real data interactive.

## Streamlit API patterns

### Charts and plotting

Streamlit has built-in chart functions, but for anything beyond the basics, use
matplotlib, plotly, or altair explicitly.

```python
# Built-in (quick and simple)
st.line_chart(df)
st.bar_chart(df)

# Matplotlib (full control over styling)
fig, ax = plt.subplots()
ax.plot(x, y)
st.pyplot(fig, width="stretch")
plt.close(fig)  # prevent memory leaks

# Plotly (interactive hover/zoom built in)
import plotly.express as px
fig = px.scatter(df, x="col1", y="col2")
st.plotly_chart(fig, use_container_width=True)
```

**Always call `plt.close(fig)` after `st.pyplot()`.** Streamlit reruns on every
interaction, so unclosed figures accumulate in memory.

**Use `width="stretch"` for st.pyplot**, not `use_container_width=True` (which is
deprecated and will be removed).

### Layout

```python
# Columns
col1, col2 = st.columns(2)
with col1:
    st.metric("Label", value)

# Tabs
tab1, tab2 = st.tabs(["View 1", "View 2"])
with tab1:
    st.write("...")

# Expander (for optional detail)
with st.expander("Show details"):
    st.write("...")
```

### Controls

```python
# Slider (numeric)
val = st.sidebar.slider("Name", min_value=0, max_value=100, value=50, step=5)

# Select box
choice = st.sidebar.selectbox("Pick one", ["a", "b", "c"])

# Multi-select
choices = st.sidebar.multiselect("Pick several", ["a", "b", "c"])

# Checkbox
show = st.sidebar.checkbox("Show extra info", value=False)

# Radio
mode = st.sidebar.radio("Mode", ["fast", "detailed"])

# Text input
query = st.sidebar.text_input("Search", "")
```

### Callouts

```python
st.info("Informational message")     # blue
st.success("Success message")        # green
st.warning("Warning message")        # yellow
st.error("Error message")            # red
```

## Styling matplotlib charts for Streamlit

Streamlit's default theme is dark. When using matplotlib, style charts to match:

```python
DARK_BG = "#0e1117"      # Streamlit's background
PANEL_BG = "#161b22"     # slightly lighter for plot area
WHITE = "#e6edf3"        # text color
MUTED = "#8b949e"        # secondary text / axis labels

fig, ax = plt.subplots(facecolor=DARK_BG)
ax.set_facecolor(PANEL_BG)
ax.set_title("Title", color=WHITE)
ax.tick_params(colors=MUTED)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["bottom"].set_color(MUTED)
ax.spines["left"].set_color(MUTED)
```

If the user wants a light theme or custom colors, adjust accordingly — but dark is
the safe default that matches Streamlit's chrome.

## Common pitfalls

**Don't use `st.set_page_config()` more than once.** It must be the first Streamlit
command in the script. If you call it again (even conditionally), the app crashes.

**Don't use browser storage APIs.** `localStorage` and `sessionStorage` are not
available. Use `st.session_state` for persisting values across reruns:
```python
if "counter" not in st.session_state:
    st.session_state.counter = 0
st.session_state.counter += 1
```

**Watch out for the rerun model.** Every widget interaction reruns the entire script
top-to-bottom. This means expensive computations must be cached, and any state you
want to persist must be in `st.session_state`.

**File paths should be relative to the script.** Use `Path(__file__).parent` to
locate data files, not `os.getcwd()` (which may differ depending on how streamlit
is launched).

## Testing

After writing the app, do a basic smoke test:

```python
python -c "
import importlib.util
# verify all imports resolve
exec(open('app_name.py').read().split('st.set_page_config')[0])
print('Imports OK')
"
```

This catches missing dependencies before the user tries to run it. You can't fully
run a Streamlit app headless in a test, but verifying imports and testing any helper
functions in isolation is worthwhile.

## Telling the user how to run it

Always include a docstring at the top of the script with the run command:

```python
"""
Description of the app.

Run with:  streamlit run app_name.py
"""
```

And remind the user in your response: `streamlit run app_name.py` — they may not
have used Streamlit before.
