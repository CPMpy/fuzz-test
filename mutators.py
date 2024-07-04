import copy
import random

from cpmpy.transformations.negation import push_down_negation
from cpmpy.transformations.to_cnf import flat2cnf

from cpmpy import intvar, Model
from cpmpy.expressions.core import Operator, Comparison
from cpmpy.transformations.decompose_global import decompose_in_tree
from cpmpy.transformations.get_variables import get_variables
from cpmpy.transformations.linearize import linearize_constraint, only_positive_bv, canonical_comparison
from cpmpy.expressions.utils import is_boolexpr, is_any_list
from cpmpy.transformations.flatten_model import flatten_constraint, normalized_boolexpr, normalized_numexpr, \
    flatten_objective, __is_flat_var
from cpmpy.transformations.normalize import toplevel_list, simplify_boolean
from cpmpy.transformations.reification import only_bv_reifies, reify_rewrite
from cpmpy.transformations.comparison import only_numexpr_equality
from cpmpy.expressions.globalconstraints import Xor


'''TRUTH TABLE BASED MORPHS'''
def not_morph(cons):
    con = random.choice(cons)
    ncon = ~con
    return [~ncon]
def xor_morph(cons):
    '''morph two constraints with XOR'''
    con1, con2 = random.choices(cons,k=2)
    #add a random option as per xor truth table
    return [random.choice((
        Xor([con1, ~con2]),
        Xor([~con1, con2]),
        ~Xor([~con1, ~con2]),
        ~Xor([con1, con2])))]

def and_morph(cons):
    '''morph two constraints with AND'''
    con1, con2 = random.choices(cons,k=2)
    return [random.choice((
        ~((con1) & (~con2)),
        ~((~con1) & (~con2)),
        ~((~con1) & (con2)),
        ((con1) & (con2))))]

def or_morph(cons):
    '''morph two constraints with OR'''
    con1, con2 = random.choices(cons,k=2)
    #add all options as per xor truth table
    return [random.choice((
        ((con1) | (~con2)),
        ~((~con1) | (~con2)),
        ((~con1) | (con2)),
        ((con1) | (con2))))]

def implies_morph(cons):
    '''morph two constraints with ->'''
    con1, con2 = random.choices(cons,k=2)
    try:
        #add all options as per xor truth table
        return [random.choice((
            ~((con1).implies(~con2)),
            ((~con1).implies(~con2)),
            ((~con1).implies(con2)),
            ((con1).implies(con2)),
            ~((con2).implies(~con1)),
            ((~con2).implies(~con1)),
            ((~con2).implies(con1)),
            ((con2).implies(con1))))]
    except Exception as e:
        raise MetamorphicError(implies_morph,cons,e)

'''CPMPY-TRANSFORMATION MORPHS'''

def canonical_comparison_morph(cons):
    n = random.randint(1, len(cons))
    randcons = random.choices(cons, k=n)
    try:
        return canonical_comparison(cons)
    except Exception as e:
        raise MetamorphicError(canonical_comparison, cons, e)

def flatten_morph(cons, flatten_all=False):
    if flatten_all is False:
        n = random.randint(1,len(cons))
        randcons = random.choices(cons,k=n)
    else:
        randcons = cons
    try:
        return flatten_constraint(randcons)
    except Exception as e:
        raise MetamorphicError(flatten_constraint,randcons, e)


def simplify_boolean_morph(cons):
    try:
        return simplify_boolean(cons)
    except Exception as e:
        raise MetamorphicError(simplify_boolean, cons, e)


def only_numexpr_equality_morph(cons,supported=frozenset()):
    n = random.randint(1, len(cons))
    randcons = random.choices(cons, k=n)
    flatcons = flatten_morph(randcons, flatten_all=True) # only_numexpr_equality requires flat constraints
    try:
        newcons = only_numexpr_equality(flatcons, supported=supported)
        return newcons
    except Exception as e:
        raise MetamorphicError(only_numexpr_equality, flatcons, e)


def normalized_boolexpr_morph(cons):
    '''normalized_boolexpr only gets called within other transformations, so can probably safely be omitted from our test.
    Keeping it in gives unwanted results, for example crashing on flatvar input'''
    randcon = random.choice(cons)
    if not __is_flat_var(randcon):
        try:
            con, newcons = normalized_boolexpr(randcon)
            return newcons + [con]
        except Exception as e:
            raise MetamorphicError(normalized_boolexpr, randcon, e)
    else:
        return cons

def normalized_numexpr_morph(const):
    try:
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        firstcon = None
        for i, con in enumerate(cons):
            res = pickaritmetic(con, log=[i])
            if res != []:
                firstcon = random.choice(res)
                break #numexpr found
        if firstcon is None:
            #no numexpressions found but still call the function to test on all inputs
            randcon = random.choice(cons)
            try:
                con, newcons = normalized_numexpr(randcon)
                return newcons + [con]
            except Exception as e:
                raise MetamorphicError(normalized_numexpr, randcon, e)
        else:
            #get the numexpr
            arg = cons[firstcon[0]]
            newfirst = arg
            for i in firstcon[1:]:
                arg = arg.args[i]
            firstexpr = arg
            try:
                con, newcons = normalized_numexpr(firstexpr)
            except Exception as e:
                raise MetamorphicError(normalized_numexpr, firstexpr, e)

            # make the new constraint (newfirst)
            arg = newfirst
            c = 1
            for i in firstcon[1:]:
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        listargs = list(arg.args)
                        listargs[i] = con
                        arg.args = tuple(listargs)
                    else:
                        arg.args[i] = con
                else:
                    arg = arg.args[i]

            return [newfirst] + newcons
    except Exception as e:
        raise MetamorphicError(normalized_numexpr_morph, cons, e)


def linearize_constraint_morph(cons,linearize_all=False,supported={}):
    if linearize_all:
        randcons = cons
    else:
        n = random.randint(1, len(cons))
        randcons = random.choices(cons, k=n)

    #only apply linearize after only_bv_reifies
    decomcons = decompose_in_tree_morph(randcons,decompose_all=True,supported=supported)
    flatcons = only_bv_reifies_morph(decomcons, morph_all=True)
    try:
        return linearize_constraint(flatcons)
    except Exception as e:
        raise MetamorphicError(linearize_constraint, flatcons, e)

def reify_rewrite_morph(cons):
    n = random.randint(1, len(cons))
    randcons = random.choices(cons, k=n)
    decomps = decompose_in_tree_morph(randcons, decompose_all=True)
    flatcons = flatten_morph(decomps, flatten_all=True)
    try:
        return reify_rewrite(flatcons)
    except Exception as e:
        raise MetamorphicError(reify_rewrite, flatcons, e)


def push_down_negation_morph(cons):
    try:
        return push_down_negation(cons)
    except Exception as e:
        raise MetamorphicError(push_down_negation, cons, e)


def flatten_objective_morph(objective):
    '''Only for optimization problems, pass the objective function, not constraints'''
    try:
        return flatten_objective(objective)
    except Exception as e:
        raise MetamorphicError(flatten_objective, objective, e)

def decompose_in_tree_morph(cons,decompose_all=False,supported={}):
    try:
        return decompose_in_tree(cons,supported=supported)
    except Exception as e:
        raise MetamorphicError(decompose_in_tree, cons, e)


def only_bv_reifies_morph(cons,morph_all=True):
    if morph_all:
        randcons = cons
    else:
        n = random.randint(1, len(cons))
        randcons = random.choices(cons, k=n)
    flatcons = flatten_morph(randcons, flatten_all=True)
    try:
        return only_bv_reifies(flatcons)
    except Exception as e:
        raise MetamorphicError(only_bv_reifies, flatcons, e)

def only_positive_bv_morph(cons):
    lincons = linearize_constraint_morph(cons,linearize_all=True,supported={})
    try:
        return only_positive_bv(lincons)
    except Exception as e:
        raise MetamorphicError(only_positive_bv, lincons, e)



def flat2cnf_morph(cons):
    #flatcons = flatten_morph(cons,flatten_all=True)
    onlycons = only_bv_reifies_morph(cons,morph_all=True)
    try:
        return flat2cnf(onlycons)
    except Exception as e:
        raise MetamorphicError(flat2cnf, onlycons, e)
def toplevel_list_morph(cons):
    try:
        return toplevel_list(cons)
    except Exception as e:
        raise MetamorphicError(toplevel_list, cons, e)


def add_solution(cons):
    vars = get_variables(cons)
    try:
        Model(cons).solve()
    except Exception as e:
        raise MetamorphicError(add_solution, cons, e)
    return [var == var.value() for var in vars if var.value() is not None]

def semanticFusion(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con,log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break #stop when 2 constraints found. still random because cons are shuffled

        if secondcon != None:
            #two constraints with aritmetic expressions found, perform semantic fusion on them
            #get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            lb,ub = Operator('sum',[firstexpr,secondexpr]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = z - secondexpr, z - firstexpr

            #make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return [] #cyclical
                c+=1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return [] #cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst,newsecond]

        else:
            #no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusion, cons, e)

def semanticFusionMinus(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con,log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break #stop when 2 constraints found. still random because cons are shuffled

        if secondcon != None:
            #two constraints with aritmetic expressions found, perform semantic fusion on them
            #get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            lb,ub = Operator('sub',[firstexpr,secondexpr]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = z + secondexpr, firstexpr - z

            #make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return [] #cyclical
                c+=1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return [] #cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst,newsecond]

        else:
            #no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionMinus, cons, e)

def semanticFusionwsum(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con,log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break #stop when 2 constraints found. still random because cons are shuffled

        if secondcon != None:
            #two constraints with aritmetic expressions found, perform semantic fusion on them
            #get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            #newsecond = copy.deepcopy(arg)
            newsecond = (arg)
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            l = random.randint(1, 10)
            n = random.randint(1, 10)
            m = random.randint(1, 10)
            lb, ub = Operator('wsum',[[l, m, n], [firstexpr, secondexpr, 1]]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = Operator('wsum',[[1, -m, -n], [z, secondexpr, 1]]) / l, Operator('wsum',[[1, -l, -n], [z, firstexpr, 1]]) / m
            #make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return [] #cyclical
                c+=1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return [] #cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst, newsecond]

        else:
            #no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionwsum, cons, e)
def semanticFusionCountingwsum(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con,log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break #stop when 2 constraints found. still random because cons are shuffled

        if secondcon != None:
            #two constraints with aritmetic expressions found, perform semantic fusion on them
            #get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            l = random.randint(1, 10)
            n = random.randint(1, 10)
            m = random.randint(1, 10)
            lb, ub = Operator('wsum',[[l, m, n], [firstexpr, secondexpr, 1]]).get_bounds()
            z = intvar(lb, ub)
            thirdcon = z == Operator('wsum', [[l, m, n], [firstexpr, secondexpr, 1]])
            firstexpr, secondexpr = Operator('wsum',[[1, -m, -n], [z, secondexpr, 1]]) / l, Operator('wsum',[[1, -l, -n], [z, firstexpr, 1]]) / m

            #make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return [] #cyclical
                c+=1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return [] #cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst, newsecond, thirdcon]

        else:
            #no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionCountingwsum, cons, e)


def semanticFusionCounting(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con,log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break #stop when 2 constraints found. still random because cons are shuffled

        if secondcon != None:
            #two constraints with aritmetic expressions found, perform semantic fusion on them
            #get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            lb,ub = Operator('sum',[firstexpr,secondexpr]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = z - secondexpr, z - firstexpr
            thirdcon = z == firstexpr + secondexpr

            #make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return [] #cyclical
                c+=1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return [] #cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst,newsecond, thirdcon]

        else:
            #no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionCounting, cons, e)

def semanticFusionCountingMinus(const):
    try:
        firstcon = None
        secondcon = None
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        for i, con in enumerate(cons):
            res = pickaritmetic(con,log=[i])
            if res != []:
                if firstcon == None:
                    firstcon = random.choice(res)
                elif secondcon == None:
                    secondcon = random.choice(res)
                    break #stop when 2 constraints found. still random because cons are shuffled

        if secondcon != None:
            #two constraints with aritmetic expressions found, perform semantic fusion on them
            #get the expressions to fuse
            arg = cons[firstcon[0]]
            newfirst = copy.deepcopy(arg)
            count = 0
            for i in firstcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(firstcon) > count + 1:
                            if firstcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            firstexpr = arg

            arg = cons[secondcon[0]]
            newsecond = arg
            count = 0
            for i in secondcon[1:]:
                count += 1
                arg = arg.args[i]
                if hasattr(arg,'name'):
                    if arg.name in ['div', 'mod', 'pow']:
                        if len(secondcon) > count + 1:
                            if secondcon[count + 1] == 1:
                                return [] #we don't want to mess with the divisor of a division, since we can't divide by a domain containing 0
            secondexpr = arg

            lb,ub = Operator('sub',[firstexpr,secondexpr]).get_bounds()
            z = intvar(lb, ub)
            firstexpr, secondexpr = z + secondexpr, firstexpr - z
            thirdcon = z == firstexpr - secondexpr
            #make the new constraints
            arg = newfirst
            c = 1
            firststr = str(firstexpr)
            for i in firstcon[1:]:
                if str(arg) in firststr:
                    return [] #cyclical
                c+=1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = firstexpr
                else:
                    arg = arg.args[i]

            arg = newsecond
            c = 1
            secondstr = str(secondexpr)
            for i in secondcon[1:]:
                if str(arg) in secondstr:
                    return [] #cyclical
                c += 1
                if c == len(secondcon):
                    if isinstance(arg.args, tuple):
                        arg.args = list(arg.args)
                    arg.args[i] = secondexpr
                else:
                    arg = arg.args[i]

            return [newfirst, newsecond, thirdcon]

        else:
            #no expressions found to fuse
            return []

    except Exception as e:
        raise MetamorphicError(semanticFusionCountingMinus, cons, e)




def aritmetic_comparison_morph(const):
    try:
        cons = copy.deepcopy(const)
        random.shuffle(cons)
        firstcon = None
        for i, con in enumerate(cons):
            res = pickaritmeticComparison(con, log=[i])
            if res != []:
                firstcon = random.choice(res)
                break  # numexpr found
        if firstcon is None:
            # no arithmetic comparisons found
            return []
        else:
            # get the expression
            arg = cons[firstcon[0]]
            newfirst = arg
            for i in firstcon[1:]:
                arg = arg.args[i]
            firstexpr = arg
            try:
                lhs = firstexpr.args[0]
                rhs = firstexpr.args[1]
                lhs1 = lhs * 7
                rhs1 = rhs * 7
                lhs2 = lhs + 7
                rhs2 = rhs + 7
                lhs3 = lhs - 7
                rhs3 = rhs - 7
                lhs, rhs = random.choice([(lhs3,rhs3),(lhs2,rhs2),(lhs1,rhs1)])
                newcon = Comparison(name=firstexpr.name,left=lhs,right=rhs)
            except Exception as e:
                raise MetamorphicError(aritmetic_comparison_morph, firstexpr, e)

            # make the new constraint (newfirst)
            arg = newfirst
            if len(firstcon) == 1: #toplevel comparison
                return [newcon]
            c = 1
            for i in firstcon[1:]:
                c += 1
                if c == len(firstcon):
                    if isinstance(arg.args, tuple):
                        listargs = list(arg.args)
                        listargs[i] = newcon
                        arg.args = tuple(listargs)
                    else:
                        arg.args[i] = newcon
                else:
                    arg = arg.args[i]

            return [newfirst]
    except Exception as e:
        raise MetamorphicError(aritmetic_comparison_morph, cons, e)

class MetamorphicError(Exception):
    pass

'''
returns a list of aritmetic expressions (as lists of indexes to traverse the expression tree)
that occur in the input expression. 
One (random) candidate is taken from each level of the expression if there exists one '''
def pickaritmetic(con,log=[], candidates=[]):
    if hasattr(con,'name'):
        if con.name == 'wsum':
            #wsum has lists as arguments so we need a separate case
            #wsum is the lowest possible level
            return candidates + [log]
        if con.name == "element":# or con.name == "table" or con.name == "cumulative":
            #no good way to know if element will return bool or not so ignore it
            return candidates
    if hasattr(con, "args"):
        iargs = [(j, e) for j, e in enumerate(con.args)]
        random.shuffle(iargs)
        for j, arg in iargs:
            if is_boolexpr(arg):
                res = pickaritmetic(arg,log+[j])
                if res != []:
                    return res
            elif is_any_list(arg):
                return pickaritmetic((arg,log+[j],candidates))
            else:
                return pickaritmetic(arg,log+[j],candidates+[log+[j]])

    return candidates

'''
Adapted pickaritmetic that only picks from arithmetic comparisons
used for mutators that i.e. multiple both sides with a number
returns a list of aritmetic expressions (as lists of indexes to traverse the expression tree)
that occur in the input expression. 
One (random) candidate is taken from each level of the expression if there exists one '''
def pickaritmeticComparison(con,log=[], candidates=[]):
    if hasattr(con,'name'):
        if con.name == 'wsum':
            #wsum has lists as arguments so we need a separate case
            #wsum is the lowest possible level
            return candidates
        if con.name == "element" or con.name == "table" or con.name == 'cumulative':
            #no good way to know if element will return bool or not so ignore it (lists and element always return false to isbool)
            return candidates
    if hasattr(con, "args"):
        iargs = [(j, e) for j, e in enumerate(con.args)]
        random.shuffle(iargs)
        for j, arg in iargs:
            if is_boolexpr(arg):
                res = pickaritmeticComparison(arg,log+[j], candidates)
                if res != []:
                    return res
            else:
                if isinstance(con,Comparison):
                    return pickaritmeticComparison(arg,log+[j],candidates+[log])
                else:
                    return pickaritmeticComparison(arg,log+[j],candidates)

    return candidates