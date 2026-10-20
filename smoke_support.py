"""Runs app.main() against the fake Streamlit so tests can read what the screens would show."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import fake_streamlit as F


def run(overrides=None, plan=(True, True), state=None):
    for m in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]:
        del sys.modules[m]
    st = F.install(overrides, state)
    import app
    app.render_auth = lambda: plan
    app._process_day_pass_return = lambda: None
    app._get_logo = lambda: ""
    try:
        app.main()
    except F.StopApp:
        pass
    return st, app
