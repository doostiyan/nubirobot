from ..models import Network


class NetworkService:

    @classmethod
    def get_all_networks(cls):
        return Network.objects.all()

    @classmethod
    def get_network_by_id(cls, network_id):
        return Network.objects.get(id=network_id)

    @classmethod
    def get_network_by_name(cls, network_name):
        return Network.objects.get(name__iexact=network_name)

    @classmethod
    def create_network(cls, name, block_limit_per_req):
        return Network.objects.create(name=name, block_limit_per_req=block_limit_per_req)

    @classmethod
    def update_network(cls, network_id, new_name, new_block_limit_per_req):
        network = cls.get_network_by_id(network_id)
        network.name = new_name
        network.max_block_per_req = new_block_limit_per_req
        network.save()
        return network

    @classmethod
    def delete_network(cls, network_id):
        Network.objects.filter(id=network_id).delete()

    @classmethod
    def get_block_time_of_network(cls, network_name):
        network = Network.objects.get(name=network_name)
        return network.block_time

    @classmethod
    def get_number_of_blocks_given_time(cls, network_name, time_s):
        network = Network.objects.get(name=network_name)
        return int(time_s / network.block_time + 1)
