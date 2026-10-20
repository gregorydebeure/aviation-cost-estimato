"""
Minimal fake of `streamlit` + `plotly` used ONLY to smoke-test app.py without a browser.
It records what the app would display (metrics, markdown, captions, warnings, charts, downloads)
so tests can compare screens with the engine and the PDF. It is not a Streamlit replacement.
"""
import sys
import types
from unittest.mock import MagicMock


class StopApp(Exception):
    pass


_MISSING = object()


class _CM:
    def __init__(self, owner):
        self._o = owner

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __getattr__(self, name):          # st.columns()[i].metric(...) etc.
        return getattr(self._o, name)


class FakeSt:
    def __init__(self, overrides=None):
        self.session_state = {}
        self.overrides = overrides or {}
        self.log = []                      # (kind, payload)
        self.widgets = []                  # (kind, label, key, disabled) — lets tests check which controls are disabled / still rendered
        self.sidebar = _CM(self)
        self.secrets = {}
        self.query_params = {}

    # ---- helpers
    def _rec(self, kind, *a, **k):
        self.log.append((kind, a, k))

    def _ov(self, label, default):
        return self.overrides.get(label, default)

    def _w(self, kind, label, k):
        self.widgets.append((kind, label, k.get("key"), bool(k.get("disabled", False))))

    # ---- layout
    def columns(self, spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_CM(self) for _ in range(n)]

    def tabs(self, labels):
        return [_CM(self) for _ in labels]

    def expander(self, *a, **k):
        self._rec("expander", *a)
        return _CM(self)

    def container(self, *a, **k):
        return _CM(self)

    def form(self, *a, **k):
        return _CM(self)

    def spinner(self, *a, **k):
        return _CM(self)

    def empty(self):
        return _CM(self)

    # ---- output
    def markdown(self, body, *a, **k): self._rec("markdown", body)
    def caption(self, body, *a, **k): self._rec("caption", body)
    def write(self, body, *a, **k): self._rec("write", body)
    def info(self, body, *a, **k): self._rec("info", body)
    def success(self, body, *a, **k): self._rec("success", body)
    def warning(self, body, *a, **k): self._rec("warning", body)
    def error(self, body, *a, **k): self._rec("error", body)
    def toast(self, body, *a, **k): self._rec("toast", body)
    def metric(self, label, value, delta=None, **k): self._rec("metric", label, value, delta)
    def dataframe(self, df, *a, **k): self._rec("dataframe", df)
    def plotly_chart(self, fig, *a, **k): self._rec("plotly_chart", fig)
    def image(self, *a, **k): pass
    def divider(self): pass
    def set_page_config(self, *a, **k): pass
    def rerun(self): raise StopApp("rerun")
    def stop(self): raise StopApp("stop")
    def download_button(self, label, data=None, *a, **k):
        self._rec("download_button", label, data, k)
        return False

    def cache_data(self, *a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

    cache_resource = cache_data

    # ---- widgets (return default or override by label)
    def button(self, label, *a, **k):
        self._w('button', label, k)
        return self._ov(label, False)
    def form_submit_button(self, label, *a, **k): return self._ov(label, False)
    def toggle(self, label, value=False, **k):
        self._w('toggle', label, k)
        return self._ov(label, value)
    def checkbox(self, label, value=False, **k):
        self._w('checkbox', label, k)
        return self._ov(label, value)

    def selectbox(self, label, options, index=0, **k):
        self._w('selectbox', label, k)
        options = list(options)
        v = self._ov(label, None)
        if v is not None:
            return v
        return options[index] if options else None

    def radio(self, label, options, index=0, **k):
        self._w('radio', label, k)
        options = list(options)
        v = self._ov(label, None)
        if v is not None:
            return v
        # Test-only legacy defaults (the screens used to start in the charter simulation with the report fuel price).
        # A test that wants the REAL defaults passes {"__real_defaults__": True}.
        if not self.overrides.get("__real_defaults__"):
            if label == "What do you want to do?":
                return options[1]
            if label == "Fuel price method":
                for o in options:
                    if str(o).startswith("Report price"):
                        return o
        return options[index] if index is not None else None

    def multiselect(self, label, options, default=None, **k):
        self._w('multiselect', label, k)
        return self._ov(label, default or [])

    def slider(self, label, min_value=0, max_value=100, value=None, *a, **k):
        self._w('slider', label, k)
        if value is None:
            value = min_value
        return self._ov(label, value)

    def number_input(self, label, min_value=None, max_value=None, value=_MISSING, *a, **k):
        self._w('number_input', label, k)
        if value is _MISSING:                 # Streamlit: omitted value = min_value; an explicit value=None = EMPTY field (returns None)
            value = min_value if min_value is not None else 0.0
        return self._ov(label, value)

    def text_input(self, label, value="", *a, **k):
        self._w('text_input', label, k)
        return self._ov(label, value)
    def text_area(self, label, value="", *a, **k): return self._ov(label, value)
    def date_input(self, label, value=None, *a, **k): return self._ov(label, value)


def install(overrides=None, state=None):
    """Install fake streamlit/plotly modules, return the FakeSt instance."""
    st = FakeSt(overrides)
    if state is not None:
        st.session_state = state
    mod = types.ModuleType("streamlit")
    for n in dir(st):
        if not n.startswith("__"):
            setattr(mod, n, getattr(st, n))
    comp_pkg = types.ModuleType("streamlit.components")
    comp_v1 = types.ModuleType("streamlit.components.v1")
    comp_v1.html = lambda *a, **k: None
    comp_pkg.v1 = comp_v1
    mod.components = comp_pkg
    sys.modules["streamlit"] = mod
    sys.modules["streamlit.components"] = comp_pkg
    sys.modules["streamlit.components.v1"] = comp_v1
    for name in ("plotly", "plotly.graph_objects", "plotly.express"):
        sys.modules[name] = MagicMock()
    sys.modules["plotly"].graph_objects = sys.modules["plotly.graph_objects"]
    sys.modules["plotly"].express = sys.modules["plotly.express"]
    return st
