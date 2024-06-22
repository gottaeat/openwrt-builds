#!/usr/bin/python3
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=too-many-branches
# pylint: disable=too-few-public-methods
# pylint: disable=missing-function-docstring
# pylint: disable=raise-missing-from
# pylint: disable=bare-except

import argparse
import logging
import os
import shutil
import sys

import jinja2
import yaml


class ANSIColors:
    RES = "\033[0;39m"

    LBLK = "\033[0;30m"
    LRED = "\033[0;31m"
    LGRN = "\033[0;32m"
    LYEL = "\033[0;33m"
    LBLU = "\033[0;34m"
    LMGN = "\033[0;35m"
    LCYN = "\033[0;36m"
    LWHI = "\033[0;37m"

    BBLK = "\033[1;30m"
    BRED = "\033[1;31m"
    BGRN = "\033[1;32m"
    BYEL = "\033[1;33m"
    BBLU = "\033[1;34m"
    BMGN = "\033[1;35m"
    BCYN = "\033[1;36m"
    BWHI = "\033[1;37m"

    def __init__(self):
        pass


_c = ANSIColors()


class ShutdownHandler(logging.StreamHandler):
    def emit(self, record):
        if record.levelno >= logging.ERROR:
            sys.exit(1)


class TemplateOpenWRTFormatter(logging.Formatter):
    _FMT_BEGIN = f"{_c.BBLK}["
    _FMT_END = f"{_c.BBLK}]{_c.BWHI}"

    _FORMATS = {
        logging.NOTSET: _c.LCYN,
        logging.DEBUG: _c.BWHI,
        logging.INFO: _c.BBLU,
        logging.WARNING: _c.LGRN,
        logging.ERROR: _c.LRED,
        logging.CRITICAL: _c.LRED,
    }

    def format(self, record):
        finfmt = f"{self._FMT_BEGIN}{self._FORMATS.get(record.levelno)}"
        finfmt += f"%(levelname)-.1s{self._FMT_END} %(message)s{_c.RES}"

        return logging.Formatter(fmt=finfmt, validate=True).format(record)


class TemplateOpenWRT:
    _VAULT_DIR = "/mnt/mss/stuff/techy-bits/git/vault/openwrt-build"

    _WRT_LIST = ["mi4a"]
    _SWITCH_LIST = []

    def __init__(self):
        self.logger = None
        self.context = None
        self.device = None
        self.device_rootfs = None
        self.config_file = None

    def _set_logger(self):
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(TemplateOpenWRTFormatter())
        self.logger = logging.getLogger("TemplateOpenWRT")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)
        self.logger.addHandler(ShutdownHandler())

    def _parse_args(self):
        parser = argparse.ArgumentParser(description="OpenWRT templator")
        parser.add_argument(
            "device",
            type=str,
            help="device name to parse the rootfs files for.",
        )
        args = parser.parse_args()

        self.device = args.device
        self.device_rootfs = f"./dir/{self.device}"
        self.config_file = f"{self._VAULT_DIR}/{self.device}_config.yml"

    def _parse_yaml(self):
        # load yaml
        if os.path.isfile(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as yaml_file:
                    yaml_parsed = yaml.load(yaml_file.read(), Loader=yaml.Loader)
            except:
                self.logger.exception("%s parsing has failed", {self.config_file})
        else:
            self.logger.error("%s is not a file or does not exist", {self.config_file})

        # check key and value presence
        required_keys = {
            "root": ["hostname", "ssh", "time"],
            "ssh": ["authorized_keys", "port"],
            "time": ["timezone", "zonename", "ntp"],
        }

        if self.device in self._WRT_LIST:
            required_keys["root"].append("radios")
            required_keys["radios"] = ["passwd", "ssid"]

        for key, value in required_keys.items():
            if key == "root":
                for item in value:
                    # pylint: disable=possibly-used-before-assignment
                    # pylint cannot understand that we exit with the logger
                    if item not in yaml_parsed.keys():
                        self.logger.error("%s is missing from the YAML", item)

                    if not yaml_parsed[item]:
                        self.logger.error("%s cannot be blank", item)

            elif key == "radios":
                if self.device == "mi4a":
                    for radio_name in ["crib", "guest"]:
                        if radio_name not in yaml_parsed["radios"].keys():
                            self.logger.error("radio name %s must be present")

                for radio in yaml_parsed["radios"].items():
                    for item in value:
                        if item not in radio[1].keys():
                            self.logger.error("%s is missing from the YAML", item)

                        if not radio[1][item]:
                            self.logger.error("%s cannot be blank", item)
            else:
                for item in value:
                    if item not in yaml_parsed[key].keys():
                        self.logger.error("%s is missing from the YAML", item)

                    if not yaml_parsed[key][item]:
                        self.logger.error("%s cannot be blank", item)

                    if item == "time":
                        if len(yaml_parsed["time"]["ntp"]) != 4:
                            self.logger.error("must provide 4 ntp servers")

                    if item == "ssh":
                        if len(yaml_parsed["ssh"]["authorized_keys"]) == 0:
                            self.logger.error("must provide at least 1 ssh key")

        self.context = yaml_parsed

    def _render(self, src, dest):
        try:
            with open(src, "r", encoding="utf-8") as file:
                template_str = file.read()
        except:
            self.logger.exception("opening %s for templating failed", src)

        try:
            template_render = jinja2.Template(template_str).render(self.context)
        except:
            self.logger.exception("templating %s failed", src)

        try:
            with open(dest, "w", encoding="utf-8") as file:
                file.write(template_render)
        except:
            self.logger.exception("writing template to %s failed", dest)

    def _copy(self):
        dest_dir = f"./work/templ_out/{self.device}"

        for root, _, files in os.walk(self.device_rootfs):
            rel_path = os.path.relpath(root, self.device_rootfs)
            dest_path = os.path.join(dest_dir, rel_path)
            os.makedirs(dest_path, exist_ok=True)

            for file in files:
                src_file_path = os.path.join(root, file)

                if file.endswith(".j2"):
                    dest_file_name = file[:-3]
                    dest_file_path = os.path.join(dest_path, dest_file_name)

                    self.logger.info("templating  : %s", dest_file_path)
                    self._render(src_file_path, dest_file_path)
                else:
                    dest_file_path = os.path.join(dest_path, file)

                    self.logger.info("copying over: %s", dest_file_path)
                    shutil.copy2(src_file_path, dest_file_path)

    def run(self):
        self._set_logger()
        self._parse_args()

        if os.path.isdir(self.device_rootfs):
            self.logger.info("templating rootfs for %s", self.device)
        else:
            self.logger.error("%s is not a recognized device", self.device)

        self._parse_yaml()
        self._copy()


if __name__ == "__main__":
    temp_owrt = TemplateOpenWRT()
    temp_owrt.run()
