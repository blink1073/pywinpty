# -*- coding: utf-8 -*-
"""Wrap process I/O pipe communication using pywin32."""

# yapf: disable

# Third party imports
import os
import re
import subprocess
import uuid

from ptyprocess.util import which

from .winpty_wrapper import PTY
import colorama
colorama.init()


class PtyProcess(object):

    def __init__(self, argv, cwd=None, env=None, dimensions=(24, 80)):
        '''Start the given command in a child process in a pseudo terminal.

        Dimensions of the psuedoterminal used for the subprocess can be
        specified as a tuple (rows, cols), or the default (24, 80) will be
        used.
        '''

        # TODO: handle system encoding.
        if not isinstance(argv, (list, tuple)):
            raise TypeError("Expected a list or tuple for argv, got %r" % argv)

        # Shallow copy of argv so we can modify it
        argv = argv[:]
        command = argv[0]

        command_with_path = which(command)
        if command_with_path is None:
            raise FileNotFoundError('The command was not found or was not ' +
                                    'executable: %s.' % command)
        command = command_with_path
        argv[0] = command

        self.proc = PTY(dimensions[1], dimensions[0])

        # Use a temporary environment while spawning.
        prev = os.environ
        if env:
            os.environ = env
        self.proc.spawn(which('cmd'), cwd=cwd or os.getcwd())
        os.environ = prev

        self._prompt = 'winspawn_prompt'
        self._end_regex = re.compile(r'winspawn_exit (\d+)')

        # Set up and send our script.
        data = 'prompt %s \r\n%s\r\necho %s\r\nexit\r\n'
        end = r'winspawn_exit %errorlevel%'
        data = data % (self._prompt, subprocess.list2cmdline(argv), end)
        self.proc.write(data)

        self.pid = uuid.uuid4().int
        self.exitstatus = None
        self._winsize = dimensions

    def close(self):
        """Close all communication process streams."""
        if self.proc:
            self.proc.close()

    def flush(self):
        '''This does nothing. It is here to support the interface for a
        File-like object. '''
        pass

    def isatty(self):
        '''This returns True if the file descriptor is open and connected to a
        tty(-like) device, else False.'''
        return self.isalive()

    def read_nonblocking(self, size=1, timeout=-1):
        '''This reads at most size characters from the child application.

        The timeout parameter is ignored.
        '''
        return self.read(size=size)

    def read(self, size=1024):
        """Read and return at most ``size`` bytes from the pty.
        """
        if not self.isalive():
            raise EOFError('Pty is closed')
        return self.proc.read(n)

    def readline(self):
        """Read one line from the pseudoterminal, and return it as unicode.

        Can block if there is nothing to read. Raises :exc:`EOFError` if the
        terminal was closed.
        """
        buf = ''
        while 1:
            if not self.isalive():
                raise EOFError('Pty is closed')
            buf += self.read(1).decode('utf-8')
            if buf.endswith('\n'):
                if self._end_regex.search(buf):
                    match = self._end_regex.search(line)
                    self.exitstatus = match.groups()[0]
                return buf

    def write(self, s):
        """Write the string ``s`` to the pseudoterminal.

        Returns the number of bytes written.
        """
        if not self.isalive():
            raise EOFError('Pty is closed')
        err, nbytes = self.proc.write(s)
        if err:
            raise IOError(err)
        return nbytes

    def terminate(self):
        '''This forces a child process to terminate.'''
        del self.proc
        self.proc = None

    def wait(self):
        '''This waits until the child exits. This is a blocking call. This will
        not read any data from the child.
        '''
        while self.isalive():
            self.readline()
        return self.exitstatus

    def isalive(self):
        '''This tests if the child process is running or not. This is
        non-blocking. If the child was terminated then this will read the
        exitstatus or signalstatus of the child. This returns True if the child
        process appears to be running or False if not.
        '''
        return self.proc and self.proc.isalive()

    def kill(self, sig):
        """Kill the process.  This is an alias to terminate.
        """
        self.terminate()

    def getwinsize(self):
        """Return the window size of the pseudoterminal as a tuple (rows, cols).
        """
        return self._winsize

    def setwinsize(self, rows, cols):
        """Set the terminal window size of the child tty.
        """
        self._winsize = (rows, cols)
        self.proc.set_size(rows, cols)



# class _winspawn(object):
#     """A class that interacts with a process on Windows.
#     """

#     def __init__(self, cmd, cwd=None, env=None):
#         """Start the process using winpty.

#         Parameters
#         ----------
#         cmd: string or list
#             The command to run.
#         cwd: string, optional
#             The cwd of the process.
#         """
#         import re
#         import colorama
#         colorama.init()

#         self.buffer = ''
#         self.returncode = 0

#         # Sentinel values to handle the output.
#         self._end_regex = re.compile(r'winspawn_exit (\d+)')
#         self._prompt = 'winspawn_prompt'
#         self._last_was_prompt = False
#         self._started = False

#         self.proc = self._create_process(cmd, cwd, env)

#     def read(self, n=1000):
#         """Read data from the pty, non-blocking.
#         """
#         data = self.proc.read(n)
#         if not data:
#             return

#         # Decode and strip the unwanted escape codes.
#         data = data.decode('utf-8')

#         # Escape codes not supported by colorama, plus the bell (\0x07).
#         to_strip = ['\x1b[?25h', '\x1b[?25l', '\x1b]0;', '\x07']
#         for code in to_strip:
#             data = data.replace(code, '')

#         # Process each line.
#         output = []
#         for line in data.splitlines():
#             line = self._handle_line(line)
#             if line:
#                 output.append(line)
#         self.buffer += '\n'.join(output)

#     def terminate(self):
#         """Terminate the process.
#         """
#         self.proc.close()
#         del self.proc

#     def isalive(self):
#         """Test if the child process is running or not.
#         """
#         return self.proc.isalive()

#     def _create_process(self, cmd, cwd, env):
#         """Start the process.
#         """
#         proc = winpty.PTY(200, 25)

#         # Use a temporary environment while spawning.
#         prev = os.environ
#         if env:
#             os.environ = env
#         proc.spawn(which('cmd'), cwd=cwd or os.getcwd())
#         os.environ = prev

#         # Set up and send our script.
#         data = 'prompt %s \r\n%s\r\necho %s\r\nexit\r\n'
#         end = r'winspawn_exit %errorlevel%'
#         data = data % (self._prompt, list2cmdline(cmd), end)
#         proc.write(data)

#         return proc

#     def _handle_line(self, line):
#         """Process a line of text.
#         """
#         # Look for a prompt, remove the line after it and
#         # signify that we've started
#         if self._prompt in line:
#             self._started = True
#             self._last_was_prompt = True
#         # Look for an exit code.
#         elif self._end_regex.search(line):
#             match = self._end_regex.search(line)
#             self.returncode = match.groups()[0]
#         # If we've started, use the line.
#         elif self._started:
#             if not self._last_was_prompt:
#                 return line
#             self._last_was_prompt = False


# proc = _winspawn(['C:/Octave/Octave-4.2.1/bin/octave-cli.exe\r\nones(3)\na=1\na++1\na\nexit\n'])
# while proc.isalive():
#     proc.read()
# proc.read()
# print(repr(proc))
# print(proc.buffer)
# print('exited with', proc.returncode)


# proc = _winspawn(['yarn'])
# while proc.isalive():
#     proc.read()
# proc.read()
# print(repr(proc.buffer))
# print(proc.buffer)
# print('exited with', proc.returncode)

# import time
# proc = _winspawn(['python'])


# time.sleep(5)
# print('close')
# proc.proc.close()

# time.sleep([5)
# print ('delete')
# del proc

# import time
# while 1:
#     time.sleep(1)


if __name__ == '__main__':
    proc = PtyProcess(['python', '--version'])
    while proc.isattyalive():
        print(proc.readline())



