"""Native desktop host for the Image2GFont workspace."""
import argparse
import json
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class DesktopAPI:
    def __init__(self, webview, workspace, url):
        self._webview = webview
        self._workspace = workspace
        self._url = url
        self._main = None
        self._panels = {}
        self._closing = False

    def detach(self, panel):
        if panel not in ('image', 'text'):
            raise ValueError('Invalid panel')
        if panel in self._panels:
            self._panels[panel].restore()
            return True
        window = self._webview.create_window(
            'Image2GFont — ' + panel, self._url + '/?panel=' + panel,
            js_api=self, width=850, height=780, min_size=(480, 400))
        self._panels[panel] = window
        window.events.closed += lambda: self._panel_closed(panel)
        return True

    def dock(self, panel):
        if panel not in ('image', 'text'):
            raise ValueError('Invalid panel')
        window = self._panels.pop(panel, None)
        if window:
            window.destroy()
        return True

    def _panel_closed(self, panel):
        self._panels.pop(panel, None)
        if not self._closing:
            self._main.evaluate_js('window.dispatchEvent(new CustomEvent("desktop-docked", {detail:' + json.dumps(panel) + '}))')

    def _can_close(self):
        with self._workspace.lock:
            busy = bool(self._workspace.job and self._workspace.job.get('status') == 'running')
            dirty = self._workspace.dirty
        if busy:
            self._main.create_confirmation_dialog('Image2GFont', '任务仍在运行，请等待任务完成后再关闭窗口。')
            return False
        if dirty and not self._main.create_confirmation_dialog('Image2GFont', '有尚未保存的修改。确定不保存并退出吗？'):
            return False
        self._closing = True
        for window in list(self._panels.values()):
            window.destroy()
        return True


def main():
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Image2GFont.Desktop')
    import webview
    from frontend_server import Workspace, make_server
    parser = argparse.ArgumentParser()
    parser.add_argument('--results')
    parser.add_argument('--smoke-test', action='store_true')
    args = parser.parse_args()
    workspace = Workspace(args.results)
    server = make_server(workspace)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    api = DesktopAPI(webview, workspace, f'http://127.0.0.1:{server.server_port}')
    window = webview.create_window('Image2GFont', api._url, js_api=api,
                                   width=1280, height=850, min_size=(960, 650),
                                   background_color='#f5f5f3')
    api._main = window
    window.events.closing += api._can_close
    webview.settings['ALLOW_DOWNLOADS'] = True
    result = {}
    def smoke():
        try:
            if not window.events.loaded.wait(40):
                raise RuntimeError('Desktop page load timed out')
            result['title'] = window.evaluate_js('document.title')
            result['bridge'] = window.evaluate_js('Boolean(window.pywebview.api.detach)')
            from urllib.request import urlopen
            with urlopen(api._url + '/api/state') as response:
                result['state_status'] = response.status
            api.detach('image')
            child = api._panels['image']
            if not child.events.loaded.wait(30):
                raise RuntimeError('Detached window load timed out')
            result['panel'] = child.evaluate_js('new URLSearchParams(location.search).get("panel")')
            from System.Drawing import Icon
            expected_icon = Icon(str(ROOT / 'frontend/logo.ico'))
            expected_bitmap = expected_icon.ToBitmap()
            try:
                for label, target in [('main', window), ('child', child)]:
                    bitmap = target.native.Icon.ToBitmap()
                    try:
                        matches = bitmap.Size == expected_bitmap.Size and all(
                            bitmap.GetPixel(x, y).ToArgb() == expected_bitmap.GetPixel(x, y).ToArgb()
                            for x in range(bitmap.Width) for y in range(bitmap.Height))
                        result[label + '_logo_matches'] = matches
                        if not matches:
                            raise RuntimeError(label + ' icon differs from Image2GFont logo')
                    finally:
                        bitmap.Dispose()
            finally:
                expected_bitmap.Dispose()
                expected_icon.Dispose()
            api.dock('image')
        except Exception as exc:
            result['error'] = str(exc)
        finally:
            window.destroy()
    try:
        webview.start(smoke if args.smoke_test else None, gui='edgechromium',
                      icon=str(ROOT / 'frontend/logo.ico'),
                      private_mode=False, storage_path=str(ROOT / 'artifacts/desktop_profile'))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    if args.smoke_test:
        result['server_stopped'] = not thread.is_alive()
        (ROOT / 'artifacts/desktop_smoke.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        if result.get('error') or not result.get('bridge'):
            raise RuntimeError(str(result))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        import ctypes
        log = ROOT / 'artifacts/desktop_startup.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(traceback.format_exc(), encoding='utf-8')
        ctypes.windll.user32.MessageBoxW(None, '启动失败，请查看：\n' + str(log), 'Image2GFont', 16)
        raise
