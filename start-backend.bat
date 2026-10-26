@echo off
cd /d %~dp0backend
if not exist .venv (
  py -3.9 -m venv .venv
)
call .venv\Scripts\activate
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
python run.py
