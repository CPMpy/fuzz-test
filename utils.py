import io
import os
import sys
import contextlib

class StdoutPipeRedirector(contextlib.AbstractContextManager):
    def __init__(self, pipe_conn):
        self.pipe_conn = pipe_conn
        self._stdout = sys.stdout
        self._stderr = sys.stderr

    def __enter__(self):
        class PipeWriter(io.TextIOBase):
            def write(_, msg):
                try:
                    self.pipe_conn.send(msg)
                except:
                    pass
                return len(msg)

        self._pipe_writer = PipeWriter()
        sys.stdout = self._pipe_writer
        sys.stderr = self._pipe_writer
        return self

    def __exit__(self, *exc):
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        # self.pipe_conn.close()