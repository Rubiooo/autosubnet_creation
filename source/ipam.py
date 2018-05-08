import netaddr
import math


def netsize(elm):
    return elm.prefixlen


class IPAM:

    def __init__(self, network_):
        self.network = netaddr.IPNetwork(network_)
        self.network_view = [self.network]
        self.allocated = []
        self.unallocated = [self.network]
        self.waiting = []

    @staticmethod
    def get_prefix(size):
        prefix = 32 - math.ceil(math.log(size, 2))
        return prefix

    def add(self, size):
        # output: CIDR string
        prefix = int(IPAM.get_prefix(size))
        flag = False
        for test_network in self.unallocated:
            if test_network.prefixlen <= prefix:
                prefix_diff = int(prefix - test_network.prefixlen)
                split_network = list(test_network.subnet(int(prefix)))
                self.allocated.append(split_network[0])
                self.unallocated.remove(test_network)
                for i in range(test_network.prefixlen + 1, prefix + 1):
                    item = list((test_network.subnet(prefixlen=i)))
                    self.unallocated.append(
                        item[1])
                flag = True
                self.update()
                return str(split_network[0])
                break
        if flag is False:
            self.waiting.append(size)
            return ""
        self.update()

    def update(self):
        self.unallocated.sort(key=netsize, reverse=True)
        self.allocated.sort(key=netsize, reverse=True)

    def delete(self, cidr):
        cidr = netaddr.IPNetwork(cidr)
        if cidr in self.allocated:
            self.allocated.remove(cidr)
            self.unallocated.append(cidr)
            self.unallocated = netaddr.cidr_merge(self.unallocated)
        self.update()
