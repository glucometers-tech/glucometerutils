from collections import namedtuple

Operation = namedtuple('Operation', ['type', 'data'])


class MockHandle(object):
    def __init__(self, padding=None):
        self.operations = iter([])
        self.padding = padding or b''

    def open(self, *args, **kwargs):
        pass

    def set_operations(self, operations):
        self.operations = iter(operations)

    def read(self, size):
        operation = next(self.operations)
        assert operation.type == 'read', operation.type
        data = operation.data
        data_len = len(data)
        padding = self.padding * (size - data_len)
        return data + padding

    def write(self, data):
        stripped_data = data.decode('latin1').rstrip('\x00').encode('latin1')
        operation = next(self.operations)
        assert operation.type == 'write'
        assert operation.data == stripped_data, 'expected {} but received {}'.format(operation.data, data)
        return len(data)
