import functools

def fib_elem_gen():
    """Генератор, возвращающий элементы ряда Фибоначчи"""
    a = 0
    b = 1

    while True:
        yield a
        res = a + b
        a = b
        b = res

g = fib_elem_gen()

while True:
    el = next(g)
    print(el)
    if el > 10:
        break
        
 
       

def my_genn():
    """Сопрограмма"""

    while True:
        number_of_fib_elem = yield
        print(number_of_fib_elem)
        
        # Генерация элементов ряда Фибоначчи
        if number_of_fib_elem <= 0:
            l = []
        elif number_of_fib_elem == 1:
            l = [0]
        else:
            l = [0, 1]
            for i in range(2, number_of_fib_elem):
                l.append(l[i-1] + l[i-2])
        
        yield l

def fib_coroutine(g):
    @functools.wraps(g)
    def inner(*args, **kwargs):
        gen = g(*args, **kwargs)
        gen.send(None)
        return gen
    return inner


my_genn = fib_coroutine(my_genn)
gen = my_genn()
print(gen.send(5))


class FibonacchiLst:
    def __init__(self, instance):
        self.instance = instance
        self.idx = 0 
        if not instance:
            max_val = 0
        else:
            try:
                max_val = max(instance)
            except (TypeError, ValueError):
                max_val = 0
        self.fib_set = self._generate_fibonacci_set(max_val)
    
    def _generate_fibonacci_set(self, max_val):
        fib_set = {0, 1}
        if max_val <= 1:
            return fib_set
        
        a, b = 0, 1
        while True:
            c = a + b
            if c > max_val:
                break
            fib_set.add(c)
            a, b = b, c
        
        return fib_set
    
    def __iter__(self):
        return self
    
    def __next__(self):
        while True:
            try:
                res = self.instance[self.idx]
                
            except IndexError:
                raise StopIteration

            if res in self.fib_set: 
                self.idx += 1
                return res

            self.idx += 1