from ...utils.exception import NotFoundException


class BlockInfoNotFoundException(NotFoundException):
    message_code = 'block_info_not_found'
