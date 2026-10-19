"""Offline end-to-end app rendering smoke test using a tiny Streamlit facade.

This does NOT replace testing an actual Streamlit Cloud deployment.
"""
from __future__ import annotations
import runpy
import sys
import types
from pathlib import Path

class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__('streamlit')
        self.sidebar=self
        self.events=[]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __getattr__(self, key):
        if key in {'tabs','columns'}:
            return lambda choices=None, *args, **kwargs: [self] * (len(choices) if isinstance(choices,list) else choices)
        if key in {'spinner','expander'}:
            return lambda *args,**kwargs: self
        if key=='cache_data':
            return lambda *args,**kwargs: (lambda function: function)
        if key=='radio':
            return lambda label, options,*args,**kwargs: options[0]
        if key=='slider':
            return lambda label, minimum, maximum, value,*args,**kwargs: value
        if key=='number_input':
            return lambda *args,**kwargs: kwargs['value']
        if key=='file_uploader':
            return lambda *args,**kwargs: None
        if key=='text_input':
            return lambda label,value,*args,**kwargs: value
        if key=='stop':
            return lambda *args,**kwargs: (_ for _ in ()).throw(RuntimeError('App unexpectedly stopped'))
        return lambda *args,**kwargs: self.events.append((key,args))

def test_app_renders_offline_stocks_only(monkeypatch):
    root=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))
    facade=FakeStreamlit()
    monkeypatch.setitem(sys.modules,'streamlit',facade)
    runpy.run_path(str(root/'app.py'), run_name='__main__')
    assert any(name=='title' and 'Stock' in args[0] for name,args in facade.events)
    assert any(name=='dataframe' for name,args in facade.events)
    assert any(name=='plotly_chart' for name,args in facade.events)
