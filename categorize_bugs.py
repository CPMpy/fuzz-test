'''
This file contains a few of the methods used to automatically categorize known bugs, in order to count how often they occured.
'''

import sys

from cpmpy.solvers import CPM_ortools
from cpmpy.solvers import CPM_minizinc

from cpmpy.expressions.utils import is_num

sys.path.append('../cpmpy')
import os
from cpmpy.expressions.variables import _IntVarImpl

from cpmpy.transformations.flatten_model import get_or_make_var_or_list, get_or_make_var
from bug_minimization import *
from cpmpy import *
from cpmpy.tools.mus import mus_naive
import copy
from metamorphic_tests import *
a = False
b = False
c = False
errormodelsolutioncheck = False
errormodelcounting = False
errormodeloptimisation = False
errormodeloptimisationsat = False
errormodelequivalence = False
b = True
if c:

    #f = 'internalcrashes\\internalfunctioncrashnormalizenumexpr'
    f = 'models\\grocery16650508470400221.bt'
    with open(f, 'rb') as fpcl:

        modle = pickle.loads(fpcl.read())
        cons = modle.constraints
        i = 1
        random.seed(i)
        reify_rewrite_morph(cons)
        #print(cons)


#read an internal crash
if a:
    i = 1
    models = glob.glob(join("minizinc-solutioncheck10", 'internal*'))
    for f in models:
        print(str(f))
        #f = 'internalfunctioncrash{}.pickle'.format(i)
        with open(f, 'rb') as fpcl:
            funct,argum,lastmodel,e, mutatorsused = pickle.loads(fpcl.read())

            '''if str(funct).__contains__('semanticFusion'):
                fpcl.close()
                name = os.path.basename(f)
                os.rename(f, f[:len(f) - len(name)] + 'semanticfusionerrors\\' + name)
            '''
            print(funct)
        #print(mis_naive(mutatorsused[21], lambda x: flatten_constraint(canonical_comparison(x))))
        mis = mis_naive(argum, funct)
        print(mis)
        print(funct(mis))


#read lasterrormodel (unsat model)
elif b:
    models = glob.glob(join("minizinc-metamorphic10", 'alldifferent_except0', 'lasterrormodel*'))
    solver = 'minizinc'
    for f in models:
        with open(f, 'rb') as fpcl:
            modle, originalmodel, mutatorsused = pickle.loads(fpcl.read())

            #if resultfile:
            #results = pickle.loads(fpcl.read())
            #print(results)

            with open(originalmodel, 'rb') as fpcl2:
                startmodel = pickle.loads(fpcl2.read())
                originalcons = startmodel.constraints

        print(originalcons,f)
        '''if str(mutatorsused).__contains__('semanticFusionwsum'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'wsumbugs\\' + name)'''
        '''if str(mutatorsused).__contains__('canonical_comparison_morph') and str(originalcons).__contains__('boolval'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)'''
        crash = False
        try:
            print(modle.solve(solver=solver, time_limit=10))
            print('success')
            continue
        except Exception as e:
            raise e
            # solve crash
            fpcl.close()
            name = os.path.basename(f)
            if str(originalcons).__contains__("alldifferent_except0"):
                if not Path(f[:len(f) - len(name)] + 'alldifferent_except0').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'alldifferent_except0')
                os.rename(f, f[:len(f) - len(name)] + 'alldifferent_except0\\' + name)
            elif str(originalcons).__contains__("count"):
                if not Path(f[:len(f) - len(name)] + 'count_in_wsum').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'count_in_wsum')
                os.rename(f, f[:len(f) - len(name)] + 'count_in_wsum\\' + name)
            else:
                if not Path(f[:len(f) - len(name)] + 'solver_crash').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'solver_crash')
                os.rename(f, f[:len(f) - len(name)] + 'solver_crash\\' + name)
            crash = True
        #assignments = modle.constraints[len(mutatorsused[-1]):]
        #print(cp.Model(mutatorsused[-1]))
        cstrsts = []
        cstrsts += [mutatorsused[0]]
        newsat = True
        notfixed = False
        if not crash:
            for x in mutatorsused:
                if isinstance(x, list):
                    #sat = (Model(x).solve())
                    #print(sat)
                    #if not sat:
                        '''if newsat:
                            # recomputing ourselfes we get sat, so we fixed something in the meantime..
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'fixed\\' + name)'''
                        '''if Model(x).solve():
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'duplicatenames\\' + name)'''
                        #mus = mus_naive(x)
                        #print(mus)
                        #Model(mus).solve()
                elif isinstance(x, float):
                    cstrsts += [x]
                    random.seed(x)
                else:
                    print(x)
                    cstrsts += [x]
                    oldconstr = cstrsts[-3]
                    cstrs = x(oldconstr)
                    cstrsts += [oldconstr + cstrs]
                    print(Model(cstrs).solve())
                    newsat = Model(oldconstr + cstrs).solve(solver=solver)

                    print(newsat)
                    if not newsat and not notfixed:
                        if str(x).__contains__("canonical_comparison_morph"):
                            fpcl.close()
                            name = os.path.basename(f)
                            if str(originalcons).__contains__('boolval'):
                                if not Path(f[:len(f) - len(name)] + 'isbool_boolval').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'isbool_boolval')
                                os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)
                            else:
                                if not Path(f[:len(f) - len(name)] + 'canonical_comparison').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'canonical_comparison')
                                os.rename(f, f[:len(f) - len(name)] + 'canonical_comparison\\' + name)
                        notfixed = True
                        break
                    #if cp.Model(cstrs).solve():
                     #   print(cp.Model(cstrs).solve())
                    #else:
                     #   print(mus_naive(cstrs))

                       # print('tadadaa', x)
                        #break
                    '''if cp.Model(cstrs+assignments).solve():
                        print(cp.Model(cstrs).solve())
                    else:
                        print(mus_naive(cstrs, assignments))
                        print('tadadaa', x)'''
            if not notfixed:
                fpcl.close()
                name = os.path.basename(f)
                os.rename(f, f[:len(f) - len(name)] + 'fixed\\' + name)

elif errormodelsolutioncheck:
    models = glob.glob(join("minizinc-solutioncheck5", 'lasterrormodel*'))
    solver = 'minizinc'
    for f in models:
        print(f)
        with open(f, 'rb') as fpcl:
            modle, originalmodel, mutatorsused = pickle.loads(fpcl.read())

            #if resultfile:
            #results = pickle.loads(fpcl.read())
            #print(results)

            with open(originalmodel, 'rb') as fpcl2:
                startmodel = pickle.loads(fpcl2.read())
                originalcons = startmodel.constraints

        #print(originalcons)
        '''if str(mutatorsused).__contains__('semanticFusionwsum'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'wsumbugs\\' + name)'''
        '''if str(mutatorsused).__contains__('canonical_comparison_morph') and str(originalcons).__contains__('boolval'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)'''
        crash = False
        try:
            print(modle.solve(solver=solver,time_limit=5))
        except Exception as e:
            print(str(e))
            # solve crash
            fpcl.close()
            name = os.path.basename(f)
            if str(originalcons).__contains__("alldifferent_except0"):
                if not Path(f[:len(f) - len(name)] + 'alldifferent_except0').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'alldifferent_except0')
                os.rename(f, f[:len(f) - len(name)] + 'alldifferent_except0\\' + name)
            elif str(originalcons).__contains__("count"):
                if not Path(f[:len(f) - len(name)] + 'count_in_wsum').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'count_in_wsum')
                os.rename(f, f[:len(f) - len(name)] + 'count_in_wsum\\' + name)
            elif str(e).__contains__("Expecting value"):
                if not Path(f[:len(f) - len(name)] + 'jsonbug').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'jsonbug')
                os.rename(f, f[:len(f) - len(name)] + 'jsonbug\\' + name)
            else:
                if not Path(f[:len(f) - len(name)] + 'solver_crash').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'solver_crash')
                os.rename(f, f[:len(f) - len(name)] + 'solver_crash\\' + name)
            crash = True
        assignments = modle.constraints[len(mutatorsused[-1]):]
        #print(cp.Model(mutatorsused[-1]))
        cstrsts = []
        cstrsts += [mutatorsused[0]]
        newsat = True
        notfixed = False
        if not crash:
            for x in mutatorsused:
                if isinstance(x, list):
                    #sat = (Model(x).solve())
                    #print(sat)
                    #if not sat:
                        '''if newsat:
                            # recomputing ourselfes we get sat, so we fixed something in the meantime..
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'fixed\\' + name)'''
                        '''if Model(x).solve():
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'duplicatenames\\' + name)'''
                        #mus = mus_naive(x)
                        #print(mus)
                        #Model(mus).solve()
                elif isinstance(x, float):
                    cstrsts += [x]
                    random.seed(x)
                else:
                    #print(x)
                    cstrsts += [x]
                    oldconstr = cstrsts[-3]
                    cstrs = x(oldconstr)
                    cstrsts += [oldconstr + cstrs]
                    newsat = Model(oldconstr + cstrs + assignments).solve(solver=solver)
                    if not newsat and not notfixed:
                        print(mus_naive(oldconstr+cstrs+assignments, solver=solver))
                        if str(x).__contains__("canonical_comparison_morph"):
                            fpcl.close()
                            name = os.path.basename(f)
                            if str(originalcons).__contains__('boolval'):
                                if not Path(f[:len(f) - len(name)] + 'isbool_boolval').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'isbool_boolval')
                                os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)
                            else:
                                if not Path(f[:len(f) - len(name)] + 'canonical_comparison').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'canonical_comparison')
                                os.rename(f, f[:len(f) - len(name)] + 'canonical_comparison\\' + name)
                            notfixed = True
                            break
                        if str(originalcons).__contains__('][l]'):
                            fpcl.close()
                            name = os.path.basename(f)
                            if not Path(f[:len(f) - len(name)] + 'element').exists():
                                os.mkdir(f[:len(f) - len(name)] + 'element')
                            os.rename(f, f[:len(f) - len(name)] + 'element\\' + name)
                        notfixed = True
                        break
                    #if cp.Model(cstrs).solve():
                     #   print(cp.Model(cstrs).solve())
                    #else:
                     #   print(mus_naive(cstrs))

                       # print('tadadaa', x)
                        #break
                    '''if cp.Model(cstrs+assignments).solve():
                        print(cp.Model(cstrs).solve())
                    else:
                        print(mus_naive(cstrs, assignments))
                        print('tadadaa', x)'''
            if not notfixed:
                fpcl.close()
                name = os.path.basename(f)
                os.rename(f, f[:len(f) - len(name)] + 'fixed\\' + name)

#read lasterrormodel (unsat model)
elif errormodelcounting:
    models = glob.glob(join("ortools-counting10", 'ortoolsunsatbug', 'lasterrormodel*'))
    solver = 'ortools'
    for f in models[:]:
        with open(f, 'rb') as fpcl:
            modle, originalmodel, mutatorsused = pickle.loads(fpcl.read())

            #if resultfile:
            #results = pickle.loads(fpcl.read())
            #print(results)
            print(f)
            with open(originalmodel, 'rb') as fpcl2:
                startmodel = pickle.loads(fpcl2.read())
                originalcons = startmodel.constraints

        print(originalcons)
        '''if str(mutatorsused).__contains__('semanticFusionwsum'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'wsumbugs\\' + name)'''
        '''if str(mutatorsused).__contains__('canonical_comparison_morph') and str(originalcons).__contains__('boolval'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)'''
        crash = False
        try:
            print(modle.solve())
            #print(modle.solve('minizinc'))
            count = modle.solveAll(solver=solver)
            print(count)
            originalcount = Model(originalcons).solveAll(solver=solver)
            print(originalcount)
        except Exception as e:
            mes = (mes_naive(modle.constraints, solver='minizinc'))
            (Model(mes, solver='minizinc').solve())
            print(mes)
            print('lalala')
            # solve crash
            raise e
            fpcl.close()
            name = os.path.basename(f)
            if not Path(f[:len(f) - len(name)] + 'solver_crash').exists():
                os.mkdir(f[:len(f) - len(name)] + 'solver_crash')
            os.rename(f, f[:len(f) - len(name)] + 'solver_crash\\' + name)
            crash = True
        #assignments = modle.constraints[len(mutatorsused[-1]):]
        #print(cp.Model(mutatorsused[-1]))
        cstrsts = []
        cstrsts += [mutatorsused[0]]
        newsat = True
        notfixed = False
        if not crash:
            for x in mutatorsused:
                if isinstance(x, list):
                    #sat = (Model(x).solve())
                    #print(sat)
                    #if not sat:
                        '''if newsat:
                            # recomputing ourselfes we get sat, so we fixed something in the meantime..
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'fixed\\' + name)'''
                        '''if Model(x).solve():
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'duplicatenames\\' + name)'''
                        #mus = mus_naive(x)
                        #print(mus)
                        #Model(mus).solve()
                elif isinstance(x, float):
                    cstrsts += [x]
                    random.seed(x)
                else:
                    print(x)
                    lastmutator = x
                    cstrsts += [x]
                    oldconstr = cstrsts[-3]
                    cstrs = x(oldconstr)
                    cstrsts += [oldconstr + cstrs]
                    newcount = Model(oldconstr + cstrs).solveAll(solver=solver)
                    print(newcount)
                    print(cstrs)
                    newsat = (newcount == originalcount)
                    if not newsat and not notfixed:
                        if str(x).__contains__("canonical_comparison_morph"):
                            fpcl.close()
                            name = os.path.basename(f)
                            if str(originalcons).__contains__('boolval'):
                                if not Path(f[:len(f) - len(name)] + 'isbool_boolval').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'isbool_boolval')
                                os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)
                            else:
                                if not Path(f[:len(f) - len(name)] + 'canonical_comparison').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'canonical_comparison')
                                os.rename(f, f[:len(f) - len(name)] + 'canonical_comparison\\' + name)
                        elif str(originalcons).__contains__('][l]'):
                            fpcl.close()
                            name = os.path.basename(f)
                            if not Path(f[:len(f) - len(name)] + 'element').exists():
                                os.mkdir(f[:len(f) - len(name)] + 'element')
                            os.rename(f, f[:len(f) - len(name)] + 'element\\' + name)
                        notfixed = True
                        break
                    #if cp.Model(cstrs).solve():
                     #   print(cp.Model(cstrs).solve())
                    #else:
                     #   print(mus_naive(cstrs))

                       # print('tadadaa', x)
                        #break
                    '''if cp.Model(cstrs+assignments).solve():
                        print(cp.Model(cstrs).solve())
                    else:
                        print(mus_naive(cstrs, assignments))
                        print('tadadaa', x)'''
            if not notfixed:
                fpcl.close()
                name = os.path.basename(f)
                os.rename(f, f[:len(f) - len(name)] + 'wsumcounting\\' + name)

elif errormodeloptimisation:
    models = glob.glob(join("minizinc-optimization10", 'solver_crash', 'lasterrormodel*'))
    solver = 'minizinc'
    for f in models[:]:
        with open(f, 'rb') as fpcl:
            modle, originalmodel, mutatorsused = pickle.loads(fpcl.read())

            #if resultfile:
            #results = pickle.loads(fpcl.read())
            #print(results)
            print(f)
            with open(originalmodel, 'rb') as fpcl2:
                startmodel = pickle.loads(fpcl2.read())
                originalcons = startmodel.constraints

        print(originalcons)
        '''if str(mutatorsused).__contains__('semanticFusionwsum'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'wsumbugs\\' + name)'''
        '''if str(mutatorsused).__contains__('canonical_comparison_morph') and str(originalcons).__contains__('boolval'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)'''
        crash = False
        try:
            sat = modle.solve(solver=solver)
            if sat:
                value = modle.objective_value()
            else:
                print(modle.solve(solver=solver))
                print(modle.solve(solver='ortools'))
                value = 0.0169
            print(value)
            objective = startmodel.objective_
            mininimize = startmodel.objective_is_min
            sat2 = startmodel.solve(solver=solver)
            if sat2:
                originalvalue = startmodel.objective_value()
            else:
                originalvalue = 0.069
            print(originalvalue)
            if value == originalvalue:
                # not an optimisation bug?
                pass
        except Exception as e:
            raise e
            print('.')
            mes = (mes_naive(modle.constraints,solver='minizinc'))
            print(get_variables(mes))
            Model(mes.solve(solver=solver))

            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            print('.')
            raise e
            # solve crash
            fpcl.close()
            name = os.path.basename(f)
            if str(originalcons).__contains__("alldifferent_except0"):
                if not Path(f[:len(f) - len(name)] + 'alldifferent_except0').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'alldifferent_except0')
                os.rename(f, f[:len(f) - len(name)] + 'alldifferent_except0\\' + name)
            elif str(originalcons).__contains__("count"):
                if not Path(f[:len(f) - len(name)] + 'count_in_wsum').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'count_in_wsum')
                os.rename(f, f[:len(f) - len(name)] + 'count_in_wsum\\' + name)
            else:
                if not Path(f[:len(f) - len(name)] + 'solver_crash').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'solver_crash')
                os.rename(f, f[:len(f) - len(name)] + 'solver_crash\\' + name)
            crash = True
        #assignments = modle.constraints[len(mutatorsused[-1]):]
        #print(cp.Model(mutatorsused[-1]))
        cstrsts = []
        cstrsts += [mutatorsused[0]]
        newsat = True
        notfixed = False
        if not crash:
            for x in mutatorsused:
                if isinstance(x, list):
                    #sat = (Model(x).solve())
                    #print(sat)
                    #if not sat:
                        '''if newsat:
                            # recomputing ourselfes we get sat, so we fixed something in the meantime..
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'fixed\\' + name)'''
                        '''if Model(x).solve():
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'duplicatenames\\' + name)'''
                        #mus = mus_naive(x)
                        #print(mus)
                        #Model(mus).solve()
                elif isinstance(x, float):
                    cstrsts += [x]
                    random.seed(x)
                else:
                    print(x)
                    lastmutator = x
                    cstrsts += [x]
                    oldconstr = cstrsts[-3]
                    cstrs = x(oldconstr)
                    cstrsts += [oldconstr + cstrs]
                    nextmodel = Model(oldconstr + cstrs)
                    if mininimize:
                        nextmodel.minimize(objective)
                    else:
                        nextmodel.maximize(objective)
                    sat1 = nextmodel.solve(solver=solver)
                    if sat1:
                        newvalue = nextmodel.objective_value()
                    else:
                        newvalue = 0.6969
                    print(newvalue)
                    newsat = (newvalue == originalvalue)
                    if not newsat and not notfixed:
                        if str(x).__contains__("canonical_comparison_morph"):
                            fpcl.close()
                            name = os.path.basename(f)
                            if str(originalcons).__contains__('boolval'):
                                if not Path(f[:len(f) - len(name)] + 'isbool_boolval').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'isbool_boolval')
                                os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)
                            else:
                                if not Path(f[:len(f) - len(name)] + 'canonical_comparison').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'canonical_comparison')
                                os.rename(f, f[:len(f) - len(name)] + 'canonical_comparison\\' + name)
                        elif str(originalcons).__contains__('][l]'):
                            fpcl.close()
                            name = os.path.basename(f)
                            if not Path(f[:len(f) - len(name)] + 'element').exists():
                                os.mkdir(f[:len(f) - len(name)] + 'element')
                            os.rename(f, f[:len(f) - len(name)] + 'element\\' + name)
                        notfixed = True
                        break
                    #if cp.Model(cstrs).solve():
                     #   print(cp.Model(cstrs).solve())
                    #else:
                     #   print(mus_naive(cstrs))

                       # print('tadadaa', x)
                        #break
                    '''if cp.Model(cstrs+assignments).solve():
                        print(cp.Model(cstrs).solve())
                    else:
                        print(mus_naive(cstrs, assignments))
                        print('tadadaa', x)'''
            if not notfixed:
                print(modle)
                print(nextmodel)
                fpcl.close()
                name = os.path.basename(f)
                os.rename(f, f[:len(f) - len(name)] + 'nochange\\' + name)

elif errormodelequivalence:
    #give appropriate name of error model
    models = glob.glob(join("minizinc-equivalence10", 'slow', 'lasterrormodel*'))
    solver = 'minizinc'
    for f in models:
        with open(f, 'rb') as fpcl:
            modle, originalmodel, mutatorsused = pickle.loads(fpcl.read())

            #if resultfile:
            #results = pickle.loads(fpcl.read())
            #print(results)
            print(f)
            with open(originalmodel, 'rb') as fpcl2:
                startmodel = pickle.loads(fpcl2.read())
                originalcons = startmodel.constraints

        print(originalcons)
        '''if str(mutatorsused).__contains__('semanticFusionwsum'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'wsumbugs\\' + name)'''
        '''if str(mutatorsused).__contains__('canonical_comparison_morph') and str(originalcons).__contains__('boolval'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)'''
        crash = False
        print('solving..')
        modle.solve(solver=solver,time_limit=5)
        print('done')
        original_vars = get_variables(originalcons)
        strvars = [str(x) for x in original_vars]
        original_solss = set()
        try:
            cp.Model(originalcons).solveAll(solver=solver, time_limit=250,
                                    display=lambda: original_solss.add((tuple(v == v.value() for v in original_vars))))
            original_sols = set()
            for x in original_solss:
                x = list(x)
                x.sort(key=lambda x: str(x))
                x = tuple(x)
                original_sols.add(x)

            sat = modle.solve(solver=solver)
        except Exception as e:
            # solve crash

            fpcl.close()
            name = os.path.basename(f)
            if str(originalcons).__contains__("alldifferent_except0"):
                if not Path(f[:len(f) - len(name)] + 'alldifferent_except0').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'alldifferent_except0')
                os.rename(f, f[:len(f) - len(name)] + 'alldifferent_except0\\' + name)

            elif not Path(f[:len(f) - len(name)] + 'solver_crash').exists():
                os.mkdir(f[:len(f) - len(name)] + 'solver_crash')
            os.rename(f, f[:len(f) - len(name)] + 'solver_crash\\' + name)
            crash = True
        #assignments = modle.constraints[len(mutatorsused[-1]):]
        #print(cp.Model(mutatorsused[-1]))
        cstrsts = []
        cstrsts += [mutatorsused[0]]
        newsat = True
        notfixed = False
        if not crash:
            for x in mutatorsused:
                if isinstance(x, list):
                    #sat = (Model(x).solve())
                    #print(sat)
                    #if not sat:
                        '''if newsat:
                            # recomputing ourselfes we get sat, so we fixed something in the meantime..
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'fixed\\' + name)'''
                        '''if Model(x).solve():
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'duplicatenames\\' + name)'''
                        #mus = mus_naive(x)
                        #print(mus)
                        #Model(mus).solve()
                elif isinstance(x, float):
                    cstrsts += [x]
                    random.seed(x)
                else:
                    print(x)
                    lastmutator = x
                    cstrsts += [x]
                    oldconstr = cstrsts[-3]
                    cstrs = x(oldconstr)
                    cstrsts += [oldconstr + cstrs]
                    nextmodel = Model(oldconstr + cstrs)
                    new_solss = set()
                    vars2 = set(get_variables(oldconstr+cstrs))
                    nextmodel.solveAll(solver=solver, display=lambda: new_solss.add(
                        tuple(var == var.value() for var in vars2 if str(var) in strvars)))
                    new_sols = set()
                    for zx in new_solss:
                        zx = list(zx)
                        zx.sort(key = lambda x: str(x))
                        zx = tuple(zx)
                        new_sols.add(zx)
                    print(original_sols)
                    print(new_sols)
                    change = new_sols ^ original_sols
                    print(len(change))
                    newsat = (len(change) == 0)
                    if not newsat and not notfixed:
                        if str(x).__contains__("canonical_comparison_morph"):
                            fpcl.close()
                            name = os.path.basename(f)
                            if str(originalcons).__contains__('boolval'):
                                if not Path(f[:len(f) - len(name)] + 'isbool_boolval').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'isbool_boolval')
                                os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)
                            else:
                                if not Path(f[:len(f) - len(name)] + 'canonical_comparison').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'canonical_comparison')
                                os.rename(f, f[:len(f) - len(name)] + 'canonical_comparison\\' + name)
                        elif str(originalcons).__contains__('][l]'):
                            fpcl.close()
                            name = os.path.basename(f)
                            if not Path(f[:len(f) - len(name)] + 'element').exists():
                                os.mkdir(f[:len(f) - len(name)] + 'element')
                            os.rename(f, f[:len(f) - len(name)] + 'element\\' + name)
                        notfixed = True
                        break
                    #if cp.Model(cstrs).solve():
                     #   print(cp.Model(cstrs).solve())
                    #else:
                     #   print(mus_naive(cstrs))

                       # print('tadadaa', x)
                        #break
                    '''if cp.Model(cstrs+assignments).solve():
                        print(cp.Model(cstrs).solve())
                    else:
                        print(mus_naive(cstrs, assignments))
                        print('tadadaa', x)'''
            if not notfixed:
                fpcl.close()
                name = os.path.basename(f)
                os.rename(f, f[:len(f) - len(name)] + 'fixed\\' + name)

elif errormodeloptimisationsat:
    models = glob.glob(join("minizinc-optimization_sat5", 'lasterrormodel*'))
    solver = 'minizinc'
    for f in models[:]:
        with open(f, 'rb') as fpcl:
            modle, originalmodel, mutatorsused = pickle.loads(fpcl.read())

            #if resultfile:
            #results = pickle.loads(fpcl.read())
            #print(results)
            print(f)
            with open(originalmodel, 'rb') as fpcl2:
                startmodel = pickle.loads(fpcl2.read())
                originalcons = startmodel.constraints

        print(originalcons)
        '''if str(mutatorsused).__contains__('semanticFusionwsum'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'wsumbugs\\' + name)'''
        '''if str(mutatorsused).__contains__('canonical_comparison_morph') and str(originalcons).__contains__('boolval'):
            fpcl.close()
            name = os.path.basename(f)
            os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)'''
        crash = False
        try:
            ovars = get_variables(startmodel.constraints)
            sat = modle.solve(solver=solver,time_limit=5)
            print(modle.objective_)
            print(modle.objective_is_min)
            print(sat)
            print([str(v) + " =" + str(v.value()) for v in ovars] )
            print(modle.status().exitstatus)
            sat = modle.solve(solver=solver)
            print(sat)
            print([str(v) + " =" + str(v.value()) for v in ovars])
            print(modle.status().exitstatus)
            if sat:
                value = modle.objective_value()
            else:
                print(sat)
                print(modle.solve(solver=solver))
                if modle.solve('ortools'):
                    name = os.path.basename(f)
                    if not Path(f[:len(f) - len(name)] + 'minizinc_unsat').exists():
                        os.mkdir(f[:len(f) - len(name)] + 'minizinc_unsat')
                    os.rename(f, f[:len(f) - len(name)] + 'minizinc_unsat\\' + name)
                value = 0.0169
            print(value)
            objective = sum(ovars)
            startmodel.objective_ = objective
            mininimize = True
            startmodel.objective_is_min = mininimize
            sat2 = startmodel.solve(solver=solver)
            if sat2:
                originalvalue = startmodel.objective_value()
            else:
                originalvalue = 0.069
            print(originalvalue)
            if value == originalvalue:
                # not an optimisation bug?
                pass
        except Exception as e:
            # solve crash
            fpcl.close()
            name = os.path.basename(f)
            if str(e).__contains__("Not a known supported ORTools left"):
                if not Path(f[:len(f) - len(name)] + 'missingcase_flatten').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'missingcase_flatten')
                os.rename(f, f[:len(f) - len(name)] + 'missingcase_flatten\\' + name)
            elif str(originalcons).__contains__("alldifferent_except0"):
                if not Path(f[:len(f) - len(name)] + 'alldifferent_except0').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'alldifferent_except0')
                os.rename(f, f[:len(f) - len(name)] + 'alldifferent_except0\\' + name)
            elif str(originalcons).__contains__("count"):
                if not Path(f[:len(f) - len(name)] + 'count_in_wsum').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'count_in_wsum')
                os.rename(f, f[:len(f) - len(name)] + 'count_in_wsum\\' + name)
            elif str(e).__contains__("Expecting value"):
                if not Path(f[:len(f) - len(name)] + 'jsonbug').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'jsonbug')
                os.rename(f, f[:len(f) - len(name)] + 'jsonbug\\' + name)

            else:
                print(e)
                if not Path(f[:len(f) - len(name)] + 'solver_crash').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'solver_crash')
                os.rename(f, f[:len(f) - len(name)] + 'solver_crash\\' + name)
            crash = True
        #assignments = modle.constraints[len(mutatorsused[-1]):]
        #print(cp.Model(mutatorsused[-1]))
        cstrsts = []
        cstrsts += [mutatorsused[0]]
        newsat = True
        notfixed = False
        if not crash:
            for x in mutatorsused:
                if isinstance(x, list):
                    #sat = (Model(x).solve())
                    #print(sat)
                    #if not sat:
                        '''if newsat:
                            # recomputing ourselfes we get sat, so we fixed something in the meantime..
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'fixed\\' + name)'''
                        '''if Model(x).solve():
                            fpcl.close()
                            name = os.path.basename(f)
                            os.rename(f, f[:len(f) - len(name)] + 'duplicatenames\\' + name)'''
                        #mus = mus_naive(x)
                        #print(mus)
                        #Model(mus).solve()
                elif isinstance(x, float):
                    cstrsts += [x]
                    random.seed(x)
                else:
                    print(x)
                    lastmutator = x
                    cstrsts += [x]
                    oldconstr = cstrsts[-3]
                    cstrs = x(oldconstr)
                    cstrsts += [oldconstr + cstrs]
                    nextmodel = Model(oldconstr + cstrs)
                    if mininimize:
                        nextmodel.minimize(objective)
                    else:
                        nextmodel.maximize(objective)
                    sat1 = nextmodel.solve(solver=solver)
                    if sat1:
                        newvalue = nextmodel.objective_value()
                    else:
                        newvalue = 0.6969
                    print(newvalue)
                    print([str(v) + " =" + str(v.value()) for v in ovars])
                    newsat = (newvalue == originalvalue)
                    if not newsat and not notfixed:
                        if str(x).__contains__("canonical_comparison_morph"):
                            fpcl.close()
                            name = os.path.basename(f)
                            if str(originalcons).__contains__('boolval'):
                                if not Path(f[:len(f) - len(name)] + 'isbool_boolval').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'isbool_boolval')
                                os.rename(f, f[:len(f) - len(name)] + 'isbool_boolval\\' + name)
                            else:
                                if not Path(f[:len(f) - len(name)] + 'canonical_comparison').exists():
                                    os.mkdir(f[:len(f) - len(name)] + 'canonical_comparison')
                                os.rename(f, f[:len(f) - len(name)] + 'canonical_comparison\\' + name)
                        elif str(originalcons).__contains__('][l]'):
                            fpcl.close()
                            name = os.path.basename(f)
                            if not Path(f[:len(f) - len(name)] + 'element').exists():
                                os.mkdir(f[:len(f) - len(name)] + 'element')
                            os.rename(f, f[:len(f) - len(name)] + 'element\\' + name)
                        notfixed = True
                        break
                    #if cp.Model(cstrs).solve():
                     #   print(cp.Model(cstrs).solve())
                    #else:
                     #   print(mus_naive(cstrs))

                       # print('tadadaa', x)
                        #break
                    '''if cp.Model(cstrs+assignments).solve():
                        print(cp.Model(cstrs).solve())
                    else:
                        print(mus_naive(cstrs, assignments))
                        print('tadadaa', x)'''
            if not notfixed:
                print(modle)
                print(nextmodel)
                fpcl.close()
                name = os.path.basename(f)
                if not Path(f[:len(f) - len(name)] + 'nochange').exists():
                    os.mkdir(f[:len(f) - len(name)] + 'nochange')
                os.rename(f, f[:len(f) - len(name)] + 'nochange\\' + name)