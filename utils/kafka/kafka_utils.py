class RoundRobinPartitioner:
    def __init__(self, partitions):
        self.partitions = partitions
        self.index = 0

    def partition(self):
        partition = self.index
        self.index = (self.index + 1) % self.partitions
        return partition


almanac_partitioner = RoundRobinPartitioner(100)

