import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from desktop_app import DesktopAPI


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.workspace = SimpleNamespace(lock=threading.RLock(), job=None, dirty=False)
        self.api = DesktopAPI(Mock(), self.workspace, 'http://127.0.0.1:1234')
        self.api._main = Mock()

    def test_reject_unknown_panel(self):
        with self.assertRaises(ValueError):
            self.api.detach('../../file')
        self.api._webview.create_window.assert_not_called()

    def test_running_task_blocks_close(self):
        self.workspace.job = {'status': 'running'}
        self.assertFalse(self.api._can_close())
        self.assertFalse(self.api._closing)

    def test_unsaved_cancel_preserves_children(self):
        self.workspace.dirty = True
        self.api._main.create_confirmation_dialog.return_value = False
        child = Mock()
        self.api._panels['image'] = child
        self.assertFalse(self.api._can_close())
        child.destroy.assert_not_called()

    def test_confirm_close_destroys_children(self):
        self.workspace.dirty = True
        self.api._main.create_confirmation_dialog.return_value = True
        child = Mock()
        self.api._panels['image'] = child
        self.assertTrue(self.api._can_close())
        child.destroy.assert_called_once()

    def test_child_close_restores_panel(self):
        self.api._panels['image'] = Mock()
        self.api._panel_closed('image')
        self.assertNotIn('image', self.api._panels)
        self.assertIn('desktop-docked', self.api._main.evaluate_js.call_args.args[0])
