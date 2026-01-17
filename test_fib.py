from gen_fib import my_genn, FibonacchiLst


def test_fib_1():
    gen = my_genn()
    assert gen.send(3) == [0, 1, 1], "Тривиальный случай n = 3, список [0, 1, 1]"


    
def test_fib_2():
    gen = my_genn()
    assert gen.send(5) == [0, 1, 1, 2, 3], "Пять первых членов ряда"

    
def test_fib_edge_case_0():
    gen = my_genn()
    assert gen.send(0) == [], "Пустой список для n = 0"


def test_fib_edge_case_1():
    gen = my_genn()
    assert gen.send(1) == [0], "Список из одного элемента для n = 1"


def test_fib_edge_case_2():
    gen = my_genn()
    assert gen.send(2) == [0, 1], "Список из двух элементов для n = 2"


def test_fib_multiple_sends():
    gen = my_genn()
    assert gen.send(3) == [0, 1, 1], "Первый вызов"
    next(gen)  
    assert gen.send(8) == [0, 1, 1, 2, 3, 5, 8, 13], "Второй вызов"
    next(gen)  
    assert gen.send(5) == [0, 1, 1, 2, 3], "Третий вызов"


def test_fibonacchi_lst_basic():
    lst = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 1]
    result = list(FibonacchiLst(lst))
    assert result == [0, 1, 2, 3, 5, 8, 1], "Проверка базового примера"


def test_fibonacchi_lst_empty():
    lst = []
    result = list(FibonacchiLst(lst))
    assert result == [], "Пустой список должен вернуть пустой результат"


def test_fibonacchi_lst_no_fibonacci():
    lst = [4, 6, 7, 9, 10, 11]
    result = list(FibonacchiLst(lst))
    assert result == [], "Список без чисел Фибоначчи должен вернуть пустой результат"


def test_fibonacchi_lst_all_fibonacci():
    lst = [0, 1, 1, 2, 3, 5, 8, 13]
    result = list(FibonacchiLst(lst))
    assert result == [0, 1, 1, 2, 3, 5, 8, 13], "Все элементы должны быть возвращены"


if __name__ == "__main__":
    tests = [
        test_fib_1,
        test_fib_2,
        test_fib_edge_case_0,
        test_fib_edge_case_1,
        test_fib_edge_case_2,
        test_fib_multiple_sends,
        test_fibonacchi_lst_basic,
        test_fibonacchi_lst_empty,
        test_fibonacchi_lst_no_fibonacci,
        test_fibonacchi_lst_all_fibonacci,
    ]
    
    print("Tests")
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            print(f"Passed: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"Assert error: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"Error {test.__name__}: {e}")
            failed += 1
    
    print(f"\n{passed} passed, {failed} failed")
    if failed == 0:
        print("All tests passed")
    else:
        exit(1)