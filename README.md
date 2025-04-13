# GeoTraceroute

A web-based geographical network path visualization tool that maps traceroute results in real-time.

## Features

* Real-time visualization of network paths
* Geographical mapping with interactive markers
* IP information enrichment with safety scores
* Asynchronous streaming processing
* Modern, responsive UI

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/jettzgg/geotraceroute.git
   cd geotraceroute
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python -m geotraceroute.main
   ```

4. Open your browser:
   ```
   http://127.0.0.1:8000
   ```

## API Key Setup

1. Sign up for a free account at [IPInfo.io](https://ipinfo.io/)
2. Get your API key from your account dashboard
3. In the GeoTraceroute web interface, click the key icon
4. Enter your API key in the settings modal

## Tech Stack

* Backend: Python, FastAPI, asyncio
* Frontend: JavaScript, Bootstrap 5, Leaflet.js

## License

MIT License