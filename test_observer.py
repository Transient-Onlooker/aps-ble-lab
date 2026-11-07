"""Mock Web Bluetooth GATT notification observer test. No real BLE device."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

html = Path(__file__).with_name("observer.html").read_text(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path="/usr/bin/chromium" if Path("/usr/bin/chromium").exists() else None
    )
    page = browser.new_page(viewport={"width": 390, "height": 844}, accept_downloads=True)
    page.evaluate("""() => {
      Object.defineProperty(window, 'isSecureContext', {value: true, configurable: true});
      class FakeCharacteristic extends EventTarget {
        constructor(uuid, props) {
          super(); this.uuid = uuid; this.properties = props;
          this.started = 0; this.stopped = 0; this.reads = 0;
        }
        async readValue() {
          this.reads++;
          return new DataView(Uint8Array.from([0,127,255]).buffer);
        }
        async startNotifications() {this.started++;return this;}
        async stopNotifications() {this.stopped++;return this;}
        async writeValue() {throw new Error('Application write forbidden in observer');}
        async writeValueWithResponse() {throw new Error('Application write forbidden in observer');}
        async writeValueWithoutResponse() {throw new Error('Application write forbidden in observer');}
      }
      const n = new FakeCharacteristic(
        '0003cdd1-0000-1000-8000-00805f9b0131',
        {notify:true,read:true,write:false});
      const w = new FakeCharacteristic(
        '0003cdd2-0000-1000-8000-00805f9b0131',
        {notify:false,read:false,write:true});
      const d = new EventTarget();
      d.name='AHG001+SYNTHETIC-TEST-ONLY';
      d.id='observer-test';
      d.gatt={
        connected:false,
        async connect(){this.connected=true;return this;},
        async getPrimaryService(uuid){
          window.selectedService=uuid;
          return {getCharacteristics:async()=>[n,w]};
        },
        disconnect(){
          this.connected=false;
          d.dispatchEvent(new Event('gattserverdisconnected'));
        }
      };
      const bt = {requestDevice:async opts=>{
        window.selectionOptions=opts; return d;
      }};
      Object.defineProperty(navigator,'bluetooth',{value:bt,configurable:true});
      window.testDevice=d;
      window.testNotification=n;
      window.firePacket=()=>{
        const evt=new Event('characteristicvaluechanged');
        Object.defineProperty(n,'value',{
          value:new DataView(Uint8Array.from([99,1,2,255,99]).buffer,1,3),
          configurable:true
        });
        n.dispatchEvent(evt);
      };
    }""")
    page.set_content(html,wait_until="load")
    assert page.locator("#choose").is_enabled()
    page.locator("#choose").click()
    assert "장치 선택 완료" in page.locator("#status").inner_text()
    filters = page.evaluate("window.selectionOptions.filters")
    assert [x["namePrefix"] for x in filters] == ["AHG001+", "BHG001+"]
    assert page.evaluate("window.selectionOptions.optionalServices") == [
        "0003cdd0-0000-1000-8000-00805f9b0131"
    ]
    assert page.locator("#connect").is_enabled()
    page.locator("#connect").click()
    assert "2개 Characteristic" in page.locator("#status").inner_text()
    assert page.evaluate("window.selectedService") == "0003cdd0-0000-1000-8000-00805f9b0131"
    assert page.locator("#characteristics button").count() == 2
    assert page.evaluate("window.testNotification.started") == 0
    assert page.evaluate("window.testNotification.reads") == 0
    page.get_by_role("button", name="Notify/Indicate 구독").click()
    assert page.evaluate("window.testNotification.started") == 1
    page.evaluate("window.firePacket()")
    assert page.evaluate("records.filter(r=>r.kind==='notify').length") == 1
    assert "01 02 FF" in page.locator("#timeline").inner_text()
    page.locator("#mark-red").click()
    page.locator("#mark-green").click()
    assert page.evaluate("records.filter(r=>r.kind==='marker').length") == 2
    page.get_by_role("button", name="일회 Read").click()
    assert "00 7F FF" in page.locator("#timeline").inner_text()
    with page.expect_download() as download_info:
        page.locator("#export").click()
    output = json.loads(Path(download_info.value.path()).read_text(encoding="utf-8"))
    assert output["format"] == "aps-ble-lab/3-notification-observer"
    assert len([r for r in output["records"] if r["kind"] == "notify"]) == 1
    assert len([r for r in output["records"] if r["kind"] == "marker"]) == 2
    assert 'SYNTHETIC-TEST-ONLY' not in json.dumps(output)
    assert 'observer-test' not in json.dumps(output)
    notify = next(r for r in output['records'] if r['kind'] == 'notify')
    assert notify['bytes'] == [1, 2, 255]
    assert notify['sessionId'] == 1
    page.get_by_role("button", name="구독 해제").click()
    assert page.evaluate("window.testNotification.stopped") == 1
    page.locator("#disconnect").click()
    assert "GATT 연결 해제됨" in page.locator("#status").inner_text()
    assert page.locator('#characteristics button').count() == 0
    page.evaluate('window.firePacket()')
    assert page.evaluate("records.filter(r=>r.kind==='notify').length") == 1
    page.locator('#connect').click()
    assert page.evaluate('sessionId') == 2
    assert page.evaluate('window.testNotification.started') == 1
    page.locator('#disconnect').click()
    print("PASS: chooser filters, GATT discover, notify, read, manual markers, JSON export, unsubscribe, disconnect; no application writes")
    browser.close()
