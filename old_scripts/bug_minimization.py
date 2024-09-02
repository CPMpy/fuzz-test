from cpmpy import Model
from cpmpy.transformations.get_variables import get_variables

def mes_naive(soft, hard=[], solver="ortools"):
    """
        Like MUS algorithm but in stead of looking for the model becoming sat
        we look for the solve call to not throw an error anymore
    """
    m = Model(hard + soft)
    no_error = False
    try:
        m.solve(solver=solver)
        no_error = True
    except Exception:
        pass
    if no_error:
        raise AssertionError("model should throw error during solve")

    mes = []
    # order so that constraints with many variables are tried and removed first
    core = sorted(soft, key=lambda c: -len(get_variables(c)))
    for i in range(len(core)):
        subcore = mes + core[i + 1:]  # check if all but 'i' makes core SAT

        try:
            Model(hard + subcore).solve(solver=solver)
            #removing it gives no more error, keep it
            mes.append(core[i])
        except:
            pass
    return mes

def mes_naive_solveAll(soft, hard=[], solver="ortools"):
    """
        Like MUS algorithm but in stead of looking for the model becoming sat
        we look for the solve call to not throw an error anymore
    """
    m = Model(hard + soft)
    no_error = False
    try:
        m.solveAll(solver=solver)
        no_error = True
    except Exception:
        pass
    if no_error:
        raise AssertionError("model should throw error during solve")

    mes = []
    # order so that constraints with many variables are tried and removed first
    core = sorted(soft, key=lambda c: -len(get_variables(c)))
    for i in range(len(core)):
        subcore = mes + core[i + 1:]  # check if all but 'i' makes core SAT

        try:
            Model(hard + subcore).solveAll(solver=solver)
            #removing it gives no more error, keep it
            mes.append(core[i])
        except:
            pass
    return mes

def mes_optimistic(soft,hard = [],solver='ortools'):
    #faster version, assuming that just 1 constraint leads to the bug. try them one by one
    m = Model(hard + soft)
    no_error = False
    try:
        m.solve(solver=solver)
        no_error = True
    except Exception:
        pass
    if no_error:
        raise AssertionError("model should throw error during solve")

    for con in reversed(soft):
        try:
            Model(hard + [con]).solve(solver=solver)
        except:
            return con

    return None #no single constraint leads to the error
def mis_naive(soft,internalfunction, hard=[]):
    """
        Like MUS algorithm but in stead of looking for the model becoming sat
        we look for the internal transformation call to not throw an error anymore
    """
    no_error = False
    try:
        internalfunction(soft + hard)
        no_error = True
    except Exception:
        pass
    if no_error:
        raise AssertionError("function call should throw error")

    mis = []
    # order so that constraints with many variables are tried and removed first
    core = sorted(soft, key=lambda c: -len(get_variables(c)))
    for i in range(len(core)):
        subcore = mis + core[i + 1:]  # check if all but 'i' makes core SAT

        try:
            internalfunction(hard + subcore)
            #removing it gives no more error, keep it
            mis.append(core[i])
        except:
            pass
    return mis

def solutions_missing(cons1,cons2,solver='ortools'):
    '''
    '''
    vars = set(get_variables(cons1))
    vars2 = set(get_variables(cons2))
    sols1 = set()
    sols2 = set()
    Model(cons2).solveAll(solver=solver,display=lambda: sols2.add(tuple(var == var.value() for var in vars2 if var in vars)))
    Model(cons1).solveAll(solver=solver,display=lambda: sols1.add(tuple(var == var.value() for var in vars)))

    disappeared = sols1 - sols2
    appeared = sols2 - sols1
    print('sols1: ' + str(len(sols1)))
    print('sols2: ' + str(len(sols2)))
    print('dis: ' + str(len(disappeared)))
    print('add: ' + str(len(appeared)))
    return appeared, disappeared

def mus_naive_counting(soft, hard=[], solver="ortools"):
    """
        A naive pure CP deletion-based MUS algorithm

        Will repeatedly solve the problem from scratch with one less constraint
        For anything but tiny sets of constraints, this will be terribly slow.

        Best to only use for testing on solvers that do not support assumptions.
        For others, use `mus()`

        :param: soft: soft constraints, list of expressions
        :param: hard: hard constraints, optional, list of expressions
        :param: solver: name of a solver, see SolverLookup.solvernames()
    """
    # ensure toplevel list

    m = Model(hard + soft)
    assert m.solveAll(solver=solver) == 0, "MUS: model must return 0 solutions"
    mus = []
    # order so that constraints with many variables are tried and removed first
    core = sorted(soft, key=lambda c: -len(get_variables(c)))
    for i in range(len(core)):
        subcore = mus + core[i + 1:]  # check if all but 'i' makes core SAT
        try:
            #print(hard + subcore)
            if Model(hard + subcore).solveAll(solver=solver)>0:
                # removing it makes it SAT, must keep for UNSAT
                mus.append(core[i])
            # else: still UNSAT so don't need this candidate
        except:
            # solver error, call mes
            mes = mes_naive(hard + subcore)
            print("messing")
            return mes

    return mus