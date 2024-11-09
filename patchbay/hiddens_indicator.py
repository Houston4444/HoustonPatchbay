
from typing import TYPE_CHECKING, Callable, Iterator, Optional, Union

from PyQt5.QtCore import pyqtSlot, QTimer
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QToolButton, QMenu, QApplication, QAction

from .cancel_mng import CancelOp, CancellableAction
from .base_group import Group
from .patchcanvas import utils
from .patchcanvas.patshared import PortMode

if TYPE_CHECKING:
    from .patchbay_manager import PatchbayManager


_translate = QApplication.translate

WHITE_LIST = -2
SHOW_ALL = -3
HIDE_ALL = -4

MENU_MIN = 3
MENU_MAX = 12


class GroupList:
    '''Used here to organize the hidden boxes menu
    when there are a lot of hidden groups.
    It tries to prevent to have very big menus.'''

    common: str
    "the common prefix for all groups inside 'list'"
    
    list: 'list[Union[Group, GroupList]]'
    'contains the list of groups or group lists.'
    
    def __init__(self, common: str,
                 group_list: 'list[Union[Group, GroupList]]'):
        self.common = common
        self.list = group_list
    
    def __repr__(self) -> str:
        return f'GroupList("{self.common}", {len(self.list)})'
    
    def walk(self) -> Iterator[tuple[list[str], Group]]:
        for group_or_list in self.list:
            if isinstance(group_or_list, Group):
                yield [], group_or_list
            else:
                for common_paths, group in group_or_list.walk():
                    yield [group_or_list.common] + common_paths, group


def common_prefix(*strings: tuple[str]) -> str:
    max_size = min([len(s) for s in strings])
    common = ''
    for i in range(max_size):
        letter_set = set([s[i] for s in strings])
        if len(letter_set) > 1:
            return common
        
        common += letter_set.pop()
        
    return common

def divide_group_list(group_list: GroupList) -> GroupList:
    if len(group_list.list) <= MENU_MAX:
        return group_list

    # At this stage group_list.list only contains groups 
    groups = list[Union[Group, GroupList]]()
    common_str = group_list.common
    common_min = len(group_list.common)
    
    for group in group_list.list:
        if len(common_str) == common_min:
            common_str = group.name
            groups.append(GroupList(common_str, [group]))
            continue
        
        common_str = common_prefix(common_str, group.name)
        if len(common_str) > common_min:
            # add this group to the last list
            groups[-1].common = common_str
            groups[-1].list.append(group)
        else:
            if len(groups[-1].list) < MENU_MIN:
                # the last list is too short
                # remove this list and add all groups directly
                last_group_list = groups.pop(-1)
                for gp in last_group_list.list:
                    groups.append(gp)
            
            common_str = group.name
            groups.append(GroupList(common_str, [group]))

    if len(groups[-1].list) < MENU_MIN:
        # the last list is too short
        # remove this list and add all groups directly
        # (only for last group)
        last_group_list = groups.pop(-1)
        for gp in last_group_list.list:
            groups.append(gp)

    # do recursion
    new_groups = list[Union[Group, GroupList]]()

    for group_or_list in groups:
        if isinstance(group_or_list, Group):
            new_groups.append(group_or_list)
        else:
            new_groups.append(divide_group_list(group_or_list))

    # recursion done
    # at this stage, list can now contains Group or GroupList objects

    # englobe directly items of childs containing less than MENU_MIN items
    new_groups_ = list[Union[Group, GroupList]]()

    for group_or_list in new_groups:
        if (isinstance(group_or_list, GroupList)
                and len(group_or_list.list) < MENU_MIN):
            for gp_or_list in group_or_list.list:
                new_groups_.append(gp_or_list)
        else:
            new_groups_.append(group_or_list)
                    
    return GroupList(group_list.common, new_groups_)


class HiddensIndicator(QToolButton):
    '''Widget used to show the number of hidden boxes.
    Exists in the tool bar, or in the filter bar (Ctrl+F),
    with different behaviors.'''
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.mng: 'PatchbayManager' = None
        self._get_filter_text: Optional[Callable[[], str]] = None
        '''If this HiddensIndicator instance is used by filter frame,
        it will only count hidden boxes matching with the filter text.'''

        self._count = 0
        self._is_blinking = False
        self._blink_timer = QTimer()
        self._blink_timer.setInterval(400)
        self._blink_timer.timeout.connect(self._blink_timer_timeout)
        
        self._BLINK_TIMES = 6
        self._blink_times_done = 0
        
        dark = '-dark' if self._is_dark() else ''

        self._icon_normal = QIcon(QPixmap(f':scalable/breeze{dark}/hint.svg'))
        self._icon_orange = QIcon(QPixmap(f':scalable/breeze{dark}/hint_orange.svg'))
        
        self.setIcon(self._icon_normal)
        
        self._menu = QMenu()
        self._menu.aboutToShow.connect(self._build_menu)
        self.setMenu(self._menu)

    def _is_dark(self) -> bool:
        return self.palette().text().color().lightnessF() > 0.5

    def set_patchbay_manager(self, mng: 'PatchbayManager'):
        self.mng = mng
        self.mng.sg.view_changed.connect(self._view_changed)
        self.mng.sg.port_types_view_changed.connect(
            self._port_types_view_changed)
        self.mng.sg.hidden_boxes_changed.connect(
            self._hidden_boxes_changed)
        self.mng.sg.group_added.connect(self._group_added)
        self.mng.sg.group_removed.connect(self._group_removed)
        self.mng.sg.all_groups_removed.connect(self._all_groups_removed)
    
    def set_filter_text_callable(self, callable: Callable[[], str]):
        self._get_filter_text = callable
    
    def set_count(self, count: int):
        self._count = count
        self.setText(str(count))
    
    def get_count(self) -> int:
        return self._count
    
    def add_one(self):
        self._count += 1
        self.setText(str(self._count))
        self._start_blink()
    
    def _start_blink(self):
        if self._blink_timer.isActive():
            return
        
        self.setIcon(self._icon_orange)
        self._blink_times_done = 1
        self._blink_timer.start()
    
    def _stop_blink(self):
        self._blink_timer.stop()
        self.setIcon(self._icon_normal)
    
    def _check_count(self):
        cg = len([g for g in self._list_hidden_groups()])
        pv_count = self._count
        self.set_count(cg)

        if not cg:
            self._stop_blink()
            return

        if (self._get_filter_text is not None
                and not self._get_filter_text()):
            self._stop_blink()
            return

        if cg > pv_count:
            self._start_blink()
    
    @pyqtSlot()
    def _blink_timer_timeout(self):
        self._blink_times_done += 1
        if self._blink_times_done % 2:
            self.setIcon(self._icon_orange)
        else:
            self.setIcon(self._icon_normal)
        
        if self._blink_times_done == self._BLINK_TIMES:
            self._blink_times_done = 0
            self._blink_timer.stop()
    
    @pyqtSlot(int)
    def _view_changed(self, view_num: int):
        self._check_count()
        
    @pyqtSlot(int)
    def _port_types_view_changed(self, port_types_flag: int):
        self._check_count()
    
    @pyqtSlot()
    def _hidden_boxes_changed(self):
        self._check_count()
    
    @pyqtSlot(int)
    def _group_added(self, group_id: int):
        group = self.mng.get_group_from_id(group_id)
        if group is None:
            return

        if group.current_position.hidden_port_modes() is PortMode.NULL:
            return

        if group.is_in_port_types_view(self.mng.port_types_view):
            self.add_one()

    @pyqtSlot(int)
    def _group_removed(self, group_id: int):
        self._check_count()
        
    @pyqtSlot()
    def _all_groups_removed(self):
        self.set_count(0)
        self._stop_blink()
    
    def _list_hidden_groups(self) -> Iterator[Group]:
        if self.mng is None:
            return
        
        flt = ''
        if self._get_filter_text is not None:
            flt = self._get_filter_text()
        
        for group in self.mng.groups:
            hpm = group.current_position.hidden_port_modes()
            if hpm is PortMode.NULL:
                continue
            
            if ((group.outs_ptv & self.mng.port_types_view
                        and PortMode.OUTPUT in hpm)
                    or (group.ins_ptv & self.mng.port_types_view
                        and PortMode.INPUT in hpm)):
                if flt:
                    if (flt.lower() in group.name.lower()
                            or flt.lower() in group.display_name.lower()):
                        yield group
                else:
                    yield group
    
    @pyqtSlot()
    def _build_menu(self):
        if self.mng is None:
            return

        menu = self.menu()
        menu.clear()
        
        dark = self._is_dark()        
        groups = [g for g in self._list_hidden_groups()]
        
        groups.sort(key=lambda x: x.name)
        group_list = divide_group_list(GroupList('', groups))
        
        menus_dict = dict[tuple[str], QMenu]()
        menus_dict[()] = menu
        
        for paths, group in group_list.walk():
            mnu = menus_dict.get(tuple(paths))
            if mnu is None:
                parent = None
                tmp_paths = paths.copy()
                while parent is None:
                    tmp_paths = tmp_paths[:-1]
                    parent = menus_dict.get(tuple(tmp_paths))
                
                while len(tmp_paths) < len(paths):
                    tmp_paths.append(paths[len(tmp_paths)])
                    mnu = QMenu(parent)
                    mnu.setTitle(tmp_paths[-1])
                    parent.addMenu(mnu)
                    menus_dict[tuple(tmp_paths)] = mnu
                    parent = mnu
                    
            group_act = mnu.addAction(group.cnv_name)
            group_act.setIcon(utils.get_icon(
                group.cnv_box_type, group.cnv_icon_name,
                group.current_position.hidden_port_modes(),
                dark=dark))
            group_act.setData(group.group_id)
            group_act.triggered.connect(self._menu_action_triggered)
        
        self.set_count(len(groups))

        menu.addSeparator()

        is_white_list = False
        view_data = self.mng.views.get(self.mng.view_number)
        if view_data is not None:
            is_white_list = view_data.is_white_list

        white_list_act = QAction(menu)
        white_list_act.setText(
            _translate('hiddens_indicator', 'Hide all new boxes'))
        white_list_act.setData(WHITE_LIST)
        white_list_act.setCheckable(True)
        white_list_act.setChecked(is_white_list)
        white_list_act.setIcon(QIcon.fromTheme('color-picker-white'))
        menu.addAction(white_list_act)

        menu.addSeparator()
        
        show_all_act = QAction(menu)
        show_all_act.setText(
            _translate('hiddens_indicator', 'Display all boxes'))
        show_all_act.setIcon(QIcon.fromTheme('visibility'))
        show_all_act.setData(SHOW_ALL)
        menu.addAction(show_all_act)
        
        hide_all_act = QAction(menu)
        hide_all_act.setText(
            _translate('hiddens_indicator', 'Hide all boxes'))
        hide_all_act.setIcon(QIcon.fromTheme('hint'))
        hide_all_act.setData(HIDE_ALL)
        
        # Do not add this action for the moment,
        # even if it works.
        # This action seems to not take sense because
        # we can select boxes and put them in a new view

        # menu.addAction(hide_all_act)
        
        for act in white_list_act, show_all_act, hide_all_act:
            act.triggered.connect(self._menu_action_triggered)

        if self._get_filter_text is not None:
            # reverse actions order for indicator in the filter frame
            acts = list[QAction]()
            for act in menu.actions():
                act.setParent(None)
                acts.append(act)
            acts.reverse()
            
            menu.clear()
            for act in acts:
                act.setParent(menu)
                menu.addAction(act)

    @pyqtSlot()
    def _menu_action_triggered(self):
        act: QAction = self.sender()
        act_data: int = act.data()
        
        if act_data == WHITE_LIST:
            with CancellableAction(self.mng, CancelOp.VIEW) as a:
                a.name = act.text()
                if act.isChecked():
                    self.mng.clear_absents_in_view()
                self.mng.view().is_white_list = act.isChecked()
                self.mng.set_views_changed()
            return
        
        if act_data == SHOW_ALL:
            with CancellableAction(self.mng, CancelOp.VIEW) as a:
                a.name = act.text()                
                self.mng.restore_all_group_hidden_sides()
            return
        
        if act_data == HIDE_ALL:
            with CancellableAction(self.mng, CancelOp.VIEW) as a:
                a.name = act.text()
                self.mng.hide_all_groups()
            return

        # act_data is now a group_id
        with CancellableAction(self.mng, CancelOp.VIEW) as a:
            a.name = _translate('undo', 'Restore "%s"') % act.text()
            self.mng.restore_group_hidden_sides(act_data)
