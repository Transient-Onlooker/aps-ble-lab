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
      testDevice.gatt={
        connected:false,
        async connect(){
          this.connected=true;
          return {connected:true,getPrimaryService:async (uuid)=>{
            window.lastGattService=uuid;
            return {uuid,getCharacteristics:async()=>[
              {uuid:'0003cdd1-0000-1000-8000-00805f9b0131',properties:{read:true,notify:true,write:false},readValue:async()=>new DataView(Uint8Array.from([0,127,255]).buffer)},
              {uuid:'0003cdd2-0000-1000-8000-00805f9b0131',properties:{read:false,write:true,notify:false}}
            ]};
          }};
        },
        disconnect(){this.connected=false;testDevice.dispatchEvent(new Event('gattserverdisconnected'));}
      };
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
    assert page.evaluate("window.lastOptions.filters.map(f => f.namePrefix)") == ["AHG001+", "BHG001+"]
    assert page.evaluate("window.lastOptions.optionalServices[0]") == "0003cdd0-0000-1000-8000-00805f9b0131"
    page.locator("#gatt-connect").click()
    assert "표준 UART 서비스 발견" in page.locator("#gatt-status").inner_text()
    assert page.evaluate("window.lastGattService") == "0003cdd0-0000-1000-8000-00805f9b0131"
    assert "00 7F FF" in page.locator("#gatt-results").inner_text()
    assert "Read 불가" in page.locator("#gatt-results").inner_text()
    page.locator("#gatt-disconnect").click()
    assert "연결 해제" in page.locator("#gatt-status").inner_text()
    page.locator("#prefix").fill("BHG001+")
    page.locator("#choose").click()
    assert page.evaluate("window.lastOptions.filters.map(f => f.namePrefix)") == ["BHG001+"]
    page.locator("#prefix").fill("AHG001+,BHG001+")
    page.locator("#chooser-all").check()
    page.locator("#choose").click()
    assert page.evaluate("window.lastOptions.acceptAllDevices") is True
    assert page.evaluate("window.lastOptions.optionalServices[0]") == "0003cdd0-0000-1000-8000-00805f9b0131"
    page.locator("#chooser-all").uncheck()
    page.locator("#scan").click()
    assert page.evaluate("window.lastScanOptions.filters.map(f => f.namePrefix)") == ["AHG001+", "BHG001+"]
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
    assert "1개 표시 / 1개 탐지" in page.locator("#count").inner_text()
    page.locator("#hide-known").check()
    assert "0개 표시 / 1개 탐지" in page.locator("#count").inner_text()
    page.locator("#hide-known").uncheck()
    assert "1개 표시 / 1개 탐지" in page.locator("#count").inner_text()
    print("PASS: dual SKE prefixes, manual prefix, optionalServices, GATT read only, disconnect, unfiltered chooser, advertisements, export, stop, clear, filters")
    browser.close()
