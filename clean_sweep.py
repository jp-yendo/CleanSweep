import sys
import os
import re
from pathlib import Path
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QCheckBox, QPushButton, QTreeWidget,
                           QTreeWidgetItem, QLabel, QFileDialog, QMessageBox,
                           QScrollArea, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon
from send2trash import send2trash
import psutil

class SearchThread(QThread):
    """ファイル検索を行うスレッド"""
    progress = pyqtSignal(str)  # 現在の検索ディレクトリを通知
    found_file = pyqtSignal(str)  # 見つかったファイルを通知
    finished = pyqtSignal()  # 検索完了を通知

    def __init__(self, selected_types, selected_dirs):
        super().__init__()
        self.selected_types = selected_types
        self.selected_dirs = selected_dirs
        self._is_running = True

        # Windowsのシステムディレクトリパターン
        # 大文字小文字を区別しないように正規表現パターンを作成
        self.system_dir_patterns = [
            re.compile(r'\\Program Files( \(x86\))?\\', re.IGNORECASE),
            re.compile(r'\\Windows\\', re.IGNORECASE),
            re.compile(r'\\AppData\\', re.IGNORECASE),
            re.compile(r'\\ProgramData\\', re.IGNORECASE),
            re.compile(r'\\Recovery\\', re.IGNORECASE),
        ]

    def is_system_directory(self, path):
        """Windowsのシステムディレクトリかどうかを判定"""
        if not self.system_dir_patterns:
            return False

        # パスをWindowsの標準形式に変換
        normalized_path = os.path.normpath(path).replace('/', '\\')
        return any(pattern.search(normalized_path) for pattern in self.system_dir_patterns)

    def stop(self):
        self._is_running = False

    def run(self):
        total_files_found = 0
        for directory in self.selected_dirs:
            if not self._is_running:
                break

            # ドライブレターの場合、ルートパスに変換
            if len(directory) == 2 and directory[1] == ':':
                directory = directory + '\\'

            self.progress.emit(f'検索中: {directory}')
            try:
                for root, dirs, files in os.walk(directory, followlinks=False):
                    if not self._is_running:
                        break

                    # Windowsのシステムディレクトリをスキップ
                    if self.is_system_directory(root):
                        dirs.clear()  # サブディレクトリの走査をスキップ
                        continue

                    # 現在のサブディレクトリを表示
                    self.progress.emit(f'検索中: {directory}\nディレクトリ: {root}')

                    for file in files:
                        if not self._is_running:
                            break

                        file_path = os.path.join(root, file)
                        for pattern in self.selected_types:
                            if pattern == 'Zone.Identifier':
                                try:
                                    # 代替データストリームの存在確認（OS非依存の方法）
                                    with open(file_path + ':Zone.Identifier', 'rb') as f:
                                        self.found_file.emit(file_path + ':Zone.Identifier')
                                        total_files_found += 1
                                except:
                                    continue
                            elif pattern == '._*':
                                if file.startswith('._'):
                                    self.found_file.emit(file_path)
                                    total_files_found += 1
                            elif file == pattern:
                                self.found_file.emit(file_path)
                                total_files_found += 1

            except PermissionError:
                continue  # アクセス権限がない場合はスキップ
            except Exception as e:
                self.progress.emit(f'エラー: {directory} - {str(e)}')
                continue

        if self._is_running:
            self.progress.emit(f'検索完了: {total_files_found}個のファイルが見つかりました')
        else:
            self.progress.emit('検索がキャンセルされました')

        self.finished.emit()

class CleanSweepApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('CleanSweep')
        self.setGeometry(100, 100, 1000, 600)
        self.setWindowIcon(QIcon('app.ico'))  # アプリケーションアイコンを設定
        self.search_thread = None

        # ウィンドウを画面中央に配置
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # メインウィジェット
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # 上部の水平レイアウト（ファイルタイプと検索対象ディレクトリ）
        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignTop)  # 上揃え

        # ファイルタイプの選択（スクロール可能）
        file_types_scroll = QScrollArea()
        file_types_scroll.setWidgetResizable(True)
        file_types_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        file_types_group = QWidget()
        file_types_layout = QVBoxLayout(file_types_group)
        file_types_layout.setAlignment(Qt.AlignTop)  # 上揃え
        file_types_layout.addWidget(QLabel('クリーンアップ対象:'))

        self.file_types = {
            'Zone.Identifier': QCheckBox('Zone.Identifier ファイル'),
            'Thumbs.db': QCheckBox('サムネイルファイル (Thumbs.db)'),
            '.DS_Store': QCheckBox('macOS システムファイル (.DS_Store)'),
            '._*': QCheckBox('macOS リソースフォーク (._*)'),
        }

        for checkbox in self.file_types.values():
            checkbox.setChecked(False)  # デフォルトでチェックなし
            file_types_layout.addWidget(checkbox)

        file_types_scroll.setWidget(file_types_group)
        top_layout.addWidget(file_types_scroll)

        # 検索対象ディレクトリ（スクロール可能）
        targets_scroll = QScrollArea()
        targets_scroll.setWidgetResizable(True)
        targets_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        targets_group = QWidget()
        targets_layout = QVBoxLayout(targets_group)
        targets_layout.setAlignment(Qt.AlignTop)  # 上揃え
        targets_layout.addWidget(QLabel('検索対象ディレクトリ:'))

        self.target_dirs = {}

        # ホームディレクトリを追加
        home = str(Path.home())
        if sys.platform == 'win32':
            self.target_dirs['HOME'] = QCheckBox(f'ユーザープロファイル ({home})')
        else:
            self.target_dirs['HOME'] = QCheckBox(f'ホームディレクトリ ({home})')

        # マウントされているディスクを検出
        for partition in psutil.disk_partitions(all=True):
            try:
                mountpoint = partition.mountpoint
                device = partition.device.rstrip('\\').rstrip('/')

                # ドライブの種類を判定
                is_network = (
                    'network' in partition.opts.lower() or
                    partition.fstype in ['nfs', 'cifs', 'smbfs'] or
                    (sys.platform == 'win32' and mountpoint.startswith('//'))
                )

                # 容量情報を取得（通常ディスクの場合のみ使用）
                size_info = ''
                if not is_network:
                    try:
                        usage = psutil.disk_usage(mountpoint)
                        size_gb = round(usage.total / (1024**3))
                        size_info = f' ({size_gb}GB)'
                    except (PermissionError, OSError):
                        pass

                # ディスク情報を表示（4パターン）
                if is_network:
                    drive_text = f'ディスク {device} (NW)'
                elif 'removable' in partition.opts.lower():
                    drive_text = f'ディスク {device}{size_info} (USB)'
                else:
                    drive_text = f'ディスク {device}{size_info}'

                self.target_dirs[device] = QCheckBox(drive_text)
            except Exception:
                # 完全にアクセスできないドライブは無視
                continue

        for checkbox in self.target_dirs.values():
            targets_layout.addWidget(checkbox)

        # カスタムディレクトリ追加ボタン
        add_dir_btn = QPushButton('ディレクトリを追加...')
        add_dir_btn.clicked.connect(self.add_custom_directory)
        targets_layout.addWidget(add_dir_btn)

        targets_scroll.setWidget(targets_group)
        top_layout.addWidget(targets_scroll)

        layout.addLayout(top_layout)

        # 検索結果表示用のツリーウィジェット
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(['ファイルパス'])  # ヘッダーを1列に変更
        self.results_tree.setColumnCount(1)  # 列数を1に設定
        layout.addWidget(self.results_tree)

        # 進捗表示
        self.progress_label = QLabel()
        self.progress_label.setWordWrap(True)  # テキストの折り返しを有効化
        self.progress_label.setFixedHeight(50)  # 固定の高さを設定
        self.progress_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 左揃え、垂直方向は中央
        progress_font = self.progress_label.font()
        progress_font.setPointSize(9)  # フォントサイズを小さく
        self.progress_label.setFont(progress_font)
        self.progress_label.hide()
        layout.addWidget(self.progress_label)

        # ボタン群
        buttons_layout = QHBoxLayout()

        self.search_btn = QPushButton('対象を検索')
        self.search_btn.clicked.connect(self.search_files)
        buttons_layout.addWidget(self.search_btn)

        self.cancel_btn = QPushButton('キャンセル')
        self.cancel_btn.clicked.connect(self.cancel_search)
        self.cancel_btn.hide()
        buttons_layout.addWidget(self.cancel_btn)

        self.select_all_btn = QPushButton('全選択')
        self.select_all_btn.clicked.connect(lambda: self.toggle_all_selections(True))
        buttons_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton('全解除')
        self.deselect_all_btn.clicked.connect(lambda: self.toggle_all_selections(False))
        buttons_layout.addWidget(self.deselect_all_btn)

        self.cleanup_btn = QPushButton('クリーンアップ')
        self.cleanup_btn.clicked.connect(self.cleanup_files)
        self.cleanup_btn.setEnabled(False)
        buttons_layout.addWidget(self.cleanup_btn)

        layout.addLayout(buttons_layout)

    def add_custom_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, 'ディレクトリを選択')
        if dir_path:
            key = f'custom_{len(self.target_dirs)}'
            self.target_dirs[key] = QCheckBox(f'カスタム: {dir_path}')
            self.target_dirs[key].setProperty('path', dir_path)
            self.target_dirs[key].setChecked(True)  # 追加時にチェックを入れる
            # レイアウトの取得を修正
            targets_layout = self.centralWidget().layout().itemAt(0).itemAt(1).widget().widget().layout()
            targets_layout.insertWidget(targets_layout.count() - 1, self.target_dirs[key])  # 追加ボタンの前に挿入

    def search_files(self):
        self.results_tree.clear()
        self.cleanup_btn.setEnabled(False)

        # 選択されたファイルタイプとディレクトリを取得
        selected_types = [k for k, v in self.file_types.items() if v.isChecked()]
        if not selected_types:
            QMessageBox.warning(self, '警告', 'クリーンアップ対象を選択してください。')
            return

        selected_dirs = []
        for checkbox in self.target_dirs.values():
            if checkbox.isChecked():
                if hasattr(checkbox, 'property') and checkbox.property('path'):
                    # カスタムディレクトリの場合
                    selected_dirs.append(checkbox.property('path'))
                else:
                    # 標準ディレクトリの場合
                    text = checkbox.text()
                    if 'ユーザープロファイル' in text or 'ホームディレクトリ' in text:
                        if sys.platform == 'win32':
                            selected_dirs.append(str(Path.home()))
                        else:
                            selected_dirs.append(str(Path.home()))
                    elif 'ディスク' in text:
                        # ドライブ文字列を抽出 (例: "ディスク C: (500GB)" から "C:" を取得)
                        drive = text.split('ディスク')[1].split()[0].strip()
                        if sys.platform == 'win32':
                            # Windows: ドライブレターを正規化
                            drive = drive.rstrip(':\\') + ':'
                        selected_dirs.append(drive)

        if not selected_dirs:
            QMessageBox.warning(self, '警告', '検索対象ディレクトリを選択してください。')
            return

        # 検索スレッドの開始
        self.search_thread = SearchThread(selected_types, selected_dirs)
        self.search_thread.progress.connect(self.update_progress)
        self.search_thread.found_file.connect(self.add_found_file)
        self.search_thread.finished.connect(self.search_finished)

        # UI状態の更新
        self.search_btn.setEnabled(False)
        self.cancel_btn.show()
        self.progress_label.show()
        self.progress_label.setText('検索を開始します...')

        self.search_thread.start()

    def cancel_search(self):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.stop()
            self.progress_label.setText('キャンセル中...')
            self.search_thread.wait()  # スレッドの終了を待機
            self.search_finished()

    def update_progress(self, message):
        # パスが長い場合は省略表示（最大80文字）
        MAX_DISPLAY_LENGTH = 80

        def truncate_path(path, prefix=''):
            # プレフィックス（"検索中: "や"サブディレクトリ: "）を考慮した実際の表示可能文字数
            available_length = MAX_DISPLAY_LENGTH - len(prefix)
            if len(path) <= available_length:
                return prefix + path

            # パスの分割
            drive = ''
            if sys.platform == 'win32' and len(path) > 2 and path[1] == ':':
                drive = path[:3]  # ドライブレター部分（例：'C:\\'）を保持
                path = path[3:]

            # 残りの長さから、先頭と末尾の表示文字数を計算
            # ドライブ文字とセパレータ('...')の長さを考慮
            remaining_length = available_length - len(drive) - 3  # 3は'...'の長さ
            head_length = remaining_length // 2
            tail_length = remaining_length - head_length

            return prefix + drive + path[:head_length] + '...' + path[-tail_length:]

        if '\n' in message:
            # 複数行のメッセージの場合
            lines = message.split('\n')
            new_lines = []
            for line in lines:
                if 'サブディレクトリ:' in line:
                    path = line.split('サブディレクトリ:')[1].strip()
                    new_lines.append(truncate_path(path, 'サブディレクトリ: '))
                elif '検索中:' in line:
                    path = line.split('検索中:')[1].strip()
                    new_lines.append(truncate_path(path, '検索中: '))
                else:
                    new_lines.append(line[:MAX_DISPLAY_LENGTH])
            message = '\n'.join(new_lines)
        elif '検索中:' in message and not message.startswith('検索完了'):
            path = message.split('検索中:')[1].strip()
            message = truncate_path(path, '検索中: ')
        elif len(message) > MAX_DISPLAY_LENGTH:
            message = message[:MAX_DISPLAY_LENGTH-3] + '...'

        self.progress_label.setText(message)

    def add_found_file(self, file_path):
        item = QTreeWidgetItem()
        item.setText(0, file_path)  # ファイルパスをそのまま表示
        item.setCheckState(0, Qt.Unchecked)
        self.results_tree.addTopLevelItem(item)
        self.cleanup_btn.setEnabled(True)  # ファイルが見つかった時点でクリーンアップボタンを有効化

    def search_finished(self):
        self.search_btn.setEnabled(True)
        self.cancel_btn.hide()
        self.progress_label.hide()
        self.cleanup_btn.setEnabled(self.results_tree.topLevelItemCount() > 0)

        if self.results_tree.topLevelItemCount() == 0:
            QMessageBox.information(self, '完了', '対象ファイルは見つかりませんでした。')

    def toggle_all_selections(self, checked):
        root = self.results_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            item.setCheckState(0, Qt.Checked if checked else Qt.Unchecked)

    def cleanup_files(self):
        root = self.results_tree.invisibleRootItem()
        selected_files = []
        error_files = []  # エラーが発生したファイルのリスト

        # 選択されたファイルを収集
        for i in range(root.childCount()):
            item = root.child(i)
            if item.checkState(0) == Qt.Checked:
                selected_files.append(item.text(0))  # パスをそのまま保持

        if not selected_files:
            QMessageBox.warning(self, '警告', '削除するファイルが選択されていません。')
            return

        # 確認ダイアログ
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText(f'{len(selected_files)}個のファイルを削除しますか？')
        msg.setInformativeText('この操作は元に戻せません。')
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        if msg.exec_() == QMessageBox.Yes:
            for file_path in selected_files:
                try:
                    if ':Zone.Identifier' in file_path:
                        # Zone.Identifierの場合は、代替データストリームを削除
                        try:
                            os.remove(file_path)
                        except PermissionError:
                            error_files.append((file_path, 'アクセス権限がありません'))
                        except FileNotFoundError:
                            error_files.append((file_path, 'ファイルが見つかりません'))
                        except OSError as e:
                            error_files.append((file_path, f'OSエラー: {str(e)}'))
                    else:
                        try:
                            send2trash(file_path)
                        except PermissionError:
                            error_files.append((file_path, 'アクセス権限がありません'))
                        except FileNotFoundError:
                            error_files.append((file_path, 'ファイルが見つかりません'))
                        except OSError as e:
                            error_files.append((file_path, f'OSエラー: {str(e)}'))
                except Exception as e:
                    error_files.append((file_path, str(e)))

            # エラーメッセージの表示
            if error_files:
                error_msg = '以下のファイルの削除中にエラーが発生しました:\n\n'
                for file_path, error in error_files:
                    error_msg += f'{file_path}\n→ {error}\n'
                QMessageBox.critical(self, 'エラー', error_msg)

            # 完了メッセージと再検索の確認
            success_count = len(selected_files) - len(error_files)
            message = f'クリーンアップが完了しました。\n成功: {success_count}件'
            if error_files:
                message += f'\n失敗: {len(error_files)}件'

            rescan_msg = QMessageBox()
            rescan_msg.setIcon(QMessageBox.Question)
            rescan_msg.setText(message)
            rescan_msg.setInformativeText('再検索を実行しますか？')
            rescan_msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            rescan_msg.setDefaultButton(QMessageBox.Yes)

            if rescan_msg.exec_() == QMessageBox.Yes:
                self.search_files()
            else:
                # 削除に成功したファイルをリストから除外
                root = self.results_tree.invisibleRootItem()
                failed_paths = [path for path, _ in error_files]
                i = 0
                while i < root.childCount():
                    item = root.child(i)
                    if item.checkState(0) == Qt.Checked and item.text(0) not in failed_paths:
                        # 削除成功したアイテムを削除
                        root.removeChild(item)
                    else:
                        # 削除失敗またはチェックされていないアイテムは次へ
                        i += 1
                # クリーンアップボタンの状態を更新
                self.cleanup_btn.setEnabled(root.childCount() > 0)

def main():
    app = QApplication(sys.argv)
    window = CleanSweepApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
