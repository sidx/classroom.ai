class LRUCache:
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.cache = {}
        self.order = []

    def update_tags(self, new_tags: list):
        new_tags.reverse()
        for tag in new_tags:
            tag = tag.strip()
            if tag in self.cache:
                # Move the tag to the front as it's the most recently used
                self.order.remove(tag)
                self.order.insert(0, tag)
            else:
                # If the cache is at capacity, remove the least recently used tag
                if len(self.order) == self.capacity:
                    lru = self.order.pop()  # Remove the least recently used from the order list
                    del self.cache[lru]  # Remove the least recently used from the cache

                # Add the new tag as the most recently used
                self.order.insert(0, tag)
                self.cache[tag] = True

    def get_cache_order(self):
        return self.order
