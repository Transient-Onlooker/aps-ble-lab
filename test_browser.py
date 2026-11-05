from pathlib import Path
from playwright.sync_api import sync_playwright

html = Path(__file__).with_name("index.html").read_text(encoding="utf-8")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path='/usr/bin/chromium' if Path('/usr/bin/chromium').exists() else None)
    page = browser.new_page(viewport={"width": 390, "height": 844}, accept_downloads=True)
    page.evaluate("""() => {
      Object.defineProperty(window,'isSecureContext',{value:true,configurable:true});
      const bt = new EventTarget();
      class FakeDevice extends EventTarget {
        constructor() {super();this.name='AHG001+BBA050E123D4+';this.id='test-device-id';}
        async watchAdvertisements(){return undefined;}
      }
      window.BluetoothDevice = FakeDevice;
      const testDevice = new FakeDevice();
      bt.requestDevice = async (opts) => {window.lastOptions=opts;return testDevice;};
      bt.requestLEScan = async (opts) => {window.lastScanOptions=opts;return {stop(){window.testStopped=true}};};
      Object.defineProperty(navigator,'bluetooth',{value:bt,configurable:true});
      window.testBT = bt;
      window.testDevice = testDevice;
    }""")
    page.set_content(html, wait_until="load")
    assert "기본 장치 선택" in page.locator("#status").inner_text()
    assert page.locator("#choose").is_enabled()
    page.locator("#choose").click()
    assert "AHG001+" in page.locator("#selection").inner_text()
    assert page.evaluate("window.lastOptions.filters[0].namePrefix") == "AHG001+"
    page.locator("#scan").click()
    assert page.evaluate("window.lastScanOptions.filters[0].namePrefix") == "AHG001+"
    page.evaluate("""() => {
      const entry={device:window.testDevice,name:window.testDevice.name,rssi:-65,txPower:-22,
       uuids:['0003cdd0-0000-1000-8000-00805f9b0131'],
       manufacturerData:new Map([[4660,new DataView(Uint8Array.from([1,2,3]).buffer)]]),
       serviceData:new Map()};
      const e=new Event('advertisementreceived');Object.assign(e,entry);window.testBT.dispatchEvent(e);
    }""")
    assert "1개 표시" in page.locator("#count").inner_text()
    assert "01 02 03" in page.locator("#results").inner_text()
    with page.expect_download() as dl:
        page.locator("#export").click()
    assert dl.value.suggested_filename.endswith(".json")
    page.locator("#stop").click()
    assert page.evaluate("window.testStopped") is True
    page.locator("#clear").click()
    assert "0개" in page.locator("#count").inner_text()
    page.locator("#scan").click()
    page.evaluate("""() => {
      const e=new Event('advertisementreceived');
      Object.assign(e,{device:{id:'known-lg',name:'AD_401_CST_570004'},name:'AD_401_CST_570004',rssi:-55,uuids:[],manufacturerData:new Map(),serviceData:new Map()});
      window.testBT.dispatchEvent(e);
    }""")
    assert "0개 표시 / 1개 탐지" in page.locator("#count").inner_text()
    page.locator("#hide-known").uncheck()
    assert "1개 표시 / 1개 탐지" in page.locator("#count").inner_text()
    print("PASS: name prefix, read-only selection, advertisements, payload, export, stop, clear, display filter")
    browser.close()
