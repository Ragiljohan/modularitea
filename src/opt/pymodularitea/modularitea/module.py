#! /usr/bin/python3

import os
import sys
import json
import getpass
from atom import Atom
from progress_adapter import FetchProgressAdapter, InstallProgressAdapter
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Vte, GLib
import platform
import apt, apt_pkg

# PREFIX = "/opt/"
PREFIX = "/home/mnirfan/Projects/"
sys.path.append(PREFIX+"modularitea/")

user = os.getenv("SUDO_USER")
# USER_MODULE_DIR = '/home/' + user + '/.modulaitea/modules/'
# SYS_MODULE_DIR = '/opt/modularitea/modules/'
USER_MODULE_DIR = PREFIX + 'modularitea/modules/'
SYS_MODULE_DIR = '/opt/modularitea/modules/'

ARCH = 32

if platform.architecture()[0] == '64bit':
    ARCH = 64


class Module:
    module = None
    apt_atoms = []
    ppas = []
    http_atoms = []
    progressbar = None

    def __init__(self, module_name, progressbar, action_label, terminal, expander):
        self.terminal = Vte.Terminal()
        self.progressbar = progressbar
        self.action_label = action_label
        self.expander = expander
        if os.path.exists(USER_MODULE_DIR + module_name):
            with open(USER_MODULE_DIR + module_name + '/package.json') as data:
                self.module = json.load(data)
        elif os.path.exists(SYS_MODULE_DIR + module_name):
            with open(SYS_MODULE_DIR + module_name + '/package.json') as data:
                self.module = json.load(data)
        else:
            print('Modul ' + module_name + " doesn't exist")
            # raise FileNotFoundError

        for atom in self.module['package']['atoms']:
            atom_temp = Atom(atom)
            print(atom_temp.object['package']['preferred_source'])
            if atom_temp.object['package']['preferred_source'] == 'ubuntu_apt':
                self.apt_atoms.append(atom_temp)
                if "ppa" in atom_temp.object['package']['source']['ubuntu_apt']:
                    self.ppas.append(atom_temp.object['package']['source']['ubuntu_apt']['ppa'])
            elif atom_temp.object['package']['preferred_source'] == 'http_archive':
                self.http_atoms.append(atom_temp)
            else:
                raise AttributeError

        print('APT      :', self.apt_atoms)
        print('Download :', self.http_atoms)
        print('PPA      :', self.ppas)

    def add_ppas(self):
        for ppa in self.ppas:
            self.action_label.set_label("Menambahkan " + ppa)
            p = self.terminal.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                "~",
                ['/usr/bin/apt-add-repository', '-y', ppa],
                [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None
            )

            if p[0] == True:
                print(ppa, "added")
            else:
                print(ppa, "failed")
                print(p[1])
        self.action_label.set_label("")

    def install_apt(self, parent):
        fprogress = FetchProgressAdapter(
            self.progressbar,
            self.action_label,
            parent
        )
        iprogress = InstallProgressAdapter(
            self.progressbar,
            self.terminal,
            self.action_label,
            self.expander
        )
        c = apt.Cache()
        self.action_label.set_label("updating software list")
        c.update(fetch_progress=fprogress)
        for package in self.apt_atoms:
            c[package.get_apt_package_name()].mark_install()
        c.commit(fetch_progress=fprogress, install_progress=iprogress)

    def download_archive(self):
        from resumable import urlretrieve
        for archive in self.http_atoms:
            print(archive.get_url(ARCH))
            urlretrieve(
                archive.get_url(ARCH),
                archive.get_name().replace(" ", ""),
                self._report_hook
            )

    def _report_hook(self, bytes_so_far, chunk_size, total_size):
        downloaded = bytes_so_far * chunk_size
        self.progressbar.set_fraction(downloaded / total_size)
        self.progressbar.set_text(
            apt_pkg.size_to_str(downloaded) + "B of " +
            apt_pkg.size_to_str(total_size) + "B"
        )

    def install_archive(self, module_name, progressbar: Gtk.ProgressBar):
        pass



if __name__ == "__main__":
    from gi.repository import Gio, GObject, GLib


    def update_cache(job, cancellable, data):
        import apt
        cache = apt.Cache()
        cache["glade"].mark_install()
        cache.commit(data[0], data[1])

    def add_ppa(job, cancellable, data):
        module = Module("coba", data[0], data[1], data[2], data[3])
        module.install_apt(None)

    def download_archive(job, cancellable, data):
        module = Module("coba", data[0], data[1], data[2], data[3])
        module.download_archive()


    GObject.threads_init()

    window = Gtk.Window(title="Test adapter")
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    window.add(box)

    label = Gtk.Label(label="Empty label")
    box.pack_start(label, 1, 1, 10)

    progressbar = Gtk.ProgressBar()
    progressbar.set_show_text(True)
    box.pack_start(progressbar, 1, 1, 10)

    vte = Vte.Terminal()
    vte.set_size_request(800, 250)

    expander = Gtk.Expander(label="tampilkan")
    expander.add(vte)
    box.pack_start(expander, 1, 1, 10)

    window.connect("delete-event", Gtk.main_quit)
    window.show_all()

    # fprogress = FetchProgressAdapter(progressbar, label, window)
    # iprogress = InstallProgressAdapter(progressbar, vte, label, expander)

    Gio.io_scheduler_push_job(download_archive,
                              (progressbar, label, vte, expander),
                              GLib.PRIORITY_DEFAULT,
                              None)
    Gtk.main()