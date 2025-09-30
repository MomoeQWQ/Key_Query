# GUI Demo

## Files
- client_gui.py: Tkinter client that loads AUI/K/config, issues queries, and displays FX+HMAC results
- server_gui.py: Tkinter controller that starts/stops multiple `csp_server` instances and shows logs

## Workflow
1) Generate index
```
python online_demo/owner_setup.py
```
2) Start CSP GUI
```
python gui_demo/server_gui.py
```
Choose `aui.pkl`, set ports (default 8001/8002/8003), click Start servers

3) Start client GUI
```
python gui_demo/client_gui.py
```
Pick `aui.pkl`, `K.pkl`, `conFig.ini`, dataset CSV; enter endpoints and query; click Run query to view results

## Tips
- Multi-keyword AND: separate keywords by spaces, e.g. `ORLANDO ENGINEERING UNIVERSITY`
- Spatial range: append `; R: lat_min,lon_min,lat_max,lon_max`
- Use the Examples button to autofill a sample query
