

import netaddr


def network_subtract(iplist1, iplist2):
    # input:  iplist1 is ip addresses list, iplist2 only has 1 element
    # output: IPNetwork list
    b = []
    if len(iplist2) == 0:
        for item in iplist1:
            b.append(netaddr.IPNetwork(item))
        b.sort(key=netsize, reverse=True)
        return b
    else:
        b = []
        for item in iplist1:
            m = netaddr.IPSet([item])
            n = netaddr.IPSet([iplist2[0]])
            result = (m - n).iter_cidrs()
            for item in result:
                if (item in b) != True:
                    b.append(item)
        b.sort(key=netsize, reverse=True)
        return b


def netsize(elm):
    # input: IPNetwork
    # output: network mask
    return elm.prefixlen


#a = network_subtract(['10.20.0.0/16'], ['10.20.0.0/26'])
# print a

#b = network_subtract(a, ['10.20.0.64/26'])
# print b
