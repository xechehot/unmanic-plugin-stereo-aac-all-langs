#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
    unmanic.stream_mapper.py

    Written by:               Josh.5 <jsunnex@gmail.com>
    Date:                     30 Jul 2021, (9:41 AM)

    Copyright:
        Copyright (C) 2021 Josh Sunnex

        This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
        Public License as published by the Free Software Foundation, version 3.

        This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the
        implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
        for more details.

        You should have received a copy of the GNU General Public License along with this program.
        If not, see <https://www.gnu.org/licenses/>.

"""
import os
import shutil
from logging import Logger

from .probe import Probe


class StreamMapper(object):
    """
    StreamMapper

    Manage FFmpeg stream mapping and generating FFmpeg command-line args.
    """

    probe: Probe = None

    stream_type_idents = {
        'video':      'v',
        'audio':      'a',
        'subtitle':   's',
        'data':       'd',
        'attachment': 't'
    }

    processing_stream_type = ''
    found_streams_to_encode = False
    stream_mapping = []
    stream_encoding = []
    video_stream_count = 0
    audio_stream_count = 0
    subtitle_stream_count = 0
    data_stream_count = 0
    attachment_stream_count = 0

    input_file = ''
    output_file = ''
    generic_options = []
    main_options = []
    advanced_options = []
    format_options = []

    def __init__(self, logger: Logger, processing_stream_type: list):
        # Ensure ffmpeg is installed
        if shutil.which('ffmpeg') is None:
            raise Exception("Unable to find executable 'ffmpeg'. Please ensure that FFmpeg is installed correctly.")

        self.logger = logger
        if processing_stream_type is not None:
            if any(pst for pst in processing_stream_type if
                   pst not in ['video', 'audio', 'subtitle', 'data', 'attachment']):
                raise Exception(
                    "processing_stream_type must be one of ['video','audio','subtitle','data','attachment']")
            self.processing_stream_type = processing_stream_type

        self.generic_options = ['-hide_banner', '-loglevel', 'info']
        self.main_options = []
        self.advanced_options = ['-strict', '-2', '-max_muxing_queue_size', '4096']

    def __copy_stream_mapping(self, codec_type, stream_id):
        self.stream_mapping += ['-map', '0:{}:{}'.format(codec_type, stream_id)]
        self.stream_encoding += ['-c:{}:{}'.format(codec_type, stream_id), 'copy']

    def __apply_custom_stream_mapping(self, mapping_dict):
        if not isinstance(mapping_dict, dict):
            raise Exception("processing_stream_type must return a dictionary")
        if 'stream_mapping' not in mapping_dict:
            raise Exception("processing_stream_type return dictionary must contain 'stream_mapping' key")
        if not isinstance(mapping_dict.get('stream_mapping'), list):
            raise Exception("processing_stream_type 'stream_mapping' value must be of type 'list'")
        if 'stream_encoding' not in mapping_dict:
            raise Exception("processing_stream_type return dictionary must contain 'stream_encoding' key")
        if not isinstance(mapping_dict.get('stream_encoding'), list):
            raise Exception("processing_stream_type 'stream_mapping' value must be of type 'list'")
        self.stream_mapping += mapping_dict.get('stream_mapping')
        self.stream_encoding += mapping_dict.get('stream_encoding')

    def set_probe(self, probe: Probe):
        self.probe = probe

    def test_stream_needs_processing(self, stream_info: dict):
        raise NotImplementedError

    def custom_stream_mapping(self, stream_info: dict, stream_id: int):
        raise NotImplementedError

    def __set_stream_mapping(self):
        file_probe_streams = self.probe.get('streams')
        if not file_probe_streams:
            return False

        processing_stream_type = self.processing_stream_type
        self.stream_mapping = []
        self.stream_encoding = []
        self.video_stream_count = 0
        self.audio_stream_count = 0
        self.subtitle_stream_count = 0
        self.data_stream_count = 0
        self.attachment_stream_count = 0

        found_streams_to_process = False

        for stream_info in file_probe_streams:
            codec_type = stream_info.get('codec_type', '').lower()

            if codec_type == "video":
                if "video" in processing_stream_type:
                    if not self.test_stream_needs_processing(stream_info):
                        self.__copy_stream_mapping('v', self.video_stream_count)
                    else:
                        mapping = self.custom_stream_mapping(stream_info, self.video_stream_count)
                        if mapping:
                            found_streams_to_process = True
                            self.__apply_custom_stream_mapping(mapping)
                        else:
                            self.__copy_stream_mapping('v', self.video_stream_count)
                    self.video_stream_count += 1
                else:
                    self.__copy_stream_mapping('v', self.video_stream_count)
                    self.video_stream_count += 1

            elif codec_type == "audio":
                if "audio" in processing_stream_type:
                    if not self.test_stream_needs_processing(stream_info):
                        self.__copy_stream_mapping('a', self.audio_stream_count)
                    else:
                        mapping = self.custom_stream_mapping(stream_info, self.audio_stream_count)
                        if mapping:
                            found_streams_to_process = True
                            self.__apply_custom_stream_mapping(mapping)
                        else:
                            self.__copy_stream_mapping('a', self.audio_stream_count)
                    self.audio_stream_count += 1
                else:
                    self.__copy_stream_mapping('a', self.audio_stream_count)
                    self.audio_stream_count += 1

            elif codec_type == "subtitle":
                if "subtitle" in processing_stream_type:
                    if not self.test_stream_needs_processing(stream_info):
                        self.__copy_stream_mapping('s', self.subtitle_stream_count)
                    else:
                        mapping = self.custom_stream_mapping(stream_info, self.subtitle_stream_count)
                        if mapping:
                            found_streams_to_process = True
                            self.__apply_custom_stream_mapping(mapping)
                        else:
                            self.__copy_stream_mapping('s', self.subtitle_stream_count)
                    self.subtitle_stream_count += 1
                else:
                    self.__copy_stream_mapping('s', self.subtitle_stream_count)
                    self.subtitle_stream_count += 1

            elif codec_type == "data":
                if "data" in processing_stream_type:
                    if not self.test_stream_needs_processing(stream_info):
                        self.__copy_stream_mapping('d', self.data_stream_count)
                    else:
                        mapping = self.custom_stream_mapping(stream_info, self.data_stream_count)
                        if mapping:
                            found_streams_to_process = True
                            self.__apply_custom_stream_mapping(mapping)
                        else:
                            self.__copy_stream_mapping('d', self.data_stream_count)
                    self.data_stream_count += 1
                else:
                    self.__copy_stream_mapping('d', self.data_stream_count)
                    self.data_stream_count += 1

            elif codec_type == "attachment":
                if "attachment" in processing_stream_type:
                    if not self.test_stream_needs_processing(stream_info):
                        self.__copy_stream_mapping('t', self.attachment_stream_count)
                    else:
                        mapping = self.custom_stream_mapping(stream_info, self.attachment_stream_count)
                        if mapping:
                            found_streams_to_process = True
                            self.__apply_custom_stream_mapping(mapping)
                        else:
                            self.__copy_stream_mapping('t', self.attachment_stream_count)
                    self.attachment_stream_count += 1
                else:
                    self.__copy_stream_mapping('t', self.attachment_stream_count)
                    self.attachment_stream_count += 1

        return found_streams_to_process

    def __build_args(self, options: list, *args, **kwargs):
        for arg in args:
            if arg in options:
                options = [value for value in options if value != arg]
                options += [arg]
            else:
                options += [arg]
        for kwarg in kwargs:
            key = kwarg
            value = kwargs.get(kwarg)
            if key in options:
                key_pos = options.index(key)
                val_pos = int(key_pos) + 1
                options[key_pos] = key
                options[val_pos] = value
            else:
                options += [key, value]
        return

    def streams_need_processing(self):
        return self.__set_stream_mapping()

    def container_needs_remuxing(self, container_extension):
        if not self.input_file:
            raise Exception("Input file not yet set")
        split_file_in = os.path.splitext(self.input_file)
        if split_file_in[1].lstrip('.') != container_extension.lstrip('.'):
            return True
        return False

    def set_input_file(self, path):
        self.input_file = os.path.abspath(path)

    def set_output_file(self, path):
        self.output_file = os.path.abspath(path)

    def set_output_null(self):
        self.output_file = '-'
        if os.name == "nt":
            self.output_file = 'NUL'
        main_options = {"-f": 'null'}
        self.__build_args(self.main_options, **main_options)

    def set_ffmpeg_generic_options(self, *args, **kwargs):
        self.__build_args(self.generic_options, *args, **kwargs)

    def set_ffmpeg_main_options(self, *args, **kwargs):
        self.__build_args(self.main_options, *args, **kwargs)

    def set_ffmpeg_advanced_options(self, *args, **kwargs):
        self.__build_args(self.advanced_options, *args, **kwargs)

    def get_stream_mapping(self):
        if not self.stream_mapping:
            self.__set_stream_mapping()
        return self.stream_mapping

    def get_stream_encoding(self):
        if not self.stream_encoding:
            self.__set_stream_mapping()
        return self.stream_encoding

    def get_ffmpeg_args(self):
        args = []
        args += self.generic_options
        args += self.main_options
        if not self.input_file:
            raise Exception("Input file has not been set")
        args += ['-i', self.input_file]
        args += self.advanced_options
        args += self.stream_mapping
        args += self.stream_encoding
        if not self.output_file:
            raise Exception("Output file has not been set")
        elif self.output_file == '-':
            args += [self.output_file]
        else:
            args += ['-y', self.output_file]
        return args
