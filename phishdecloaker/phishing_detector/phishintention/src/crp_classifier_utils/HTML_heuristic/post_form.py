from lxml import html
import io
import os
import numpy as np

def read_html(html_code):
    '''
    read html and parse into tree
    :param html_path: path to html.txt
    '''
    tree_list = None
    
    # parse html text
    try:
        tree = html.fromstring(html_code)
        tree_list = tree
    except Exception as e:
        pass

    return tree_list

def proc_tree(tree, obfuscate=False):
    '''
    returns number of forms, type of forms in a list, number of inputs in each form, number of password field in each form
    :param tree: Element html object
    '''
    
    if tree is None: # parsing into tree failed
        return 0, [], [], [], []
    forms = tree.xpath('.//form') # find form
    if len(forms) == 0 : # no form
        return 0, [], [], [], []
    else:
        if obfuscate:
            for form in forms:
                inputs = form.xpath('.//input')
                for input in inputs:
                    try:
                        if input.get('type') == "password":
                            input.attrib['type'] = "passw0rd"
                    except:
                        pass

        methods  = []
        count_inputs = []
        count_password = []
        count_username = []
        
        for form in forms:
            count = 0
            methods.append(form.get('method')) # get method of form "post"/"get"
            
            inputs = form.xpath('.//input')
            count_inputs.append(len(inputs)) # get number if inputs
            inputs = form.xpath('.//input[@type="password"]') # get number of password fields
            inputs2 = form.xpath('.//input[@name="password" and @type!="hidden" and @type!="search" and not(contains(@placeholder, "search")) and @aria-label!="search" and @title!="search"]')
            count_password.append(len(inputs) + len(inputs2))

            usernames = form.xpath('.//input[@type="username"]') # get number of username fields
            usernames2 = form.xpath('.//input[@name="username" and @type!="hidden" and @type!="search" and not(contains(@placeholder, "search")) and @aria-label!="search" and @title!="search"]') # get number of username fields
            count_username.append(len(usernames) + len(usernames2))

        return len(forms), methods, count_inputs, count_password, count_username
            
        
def check_post(x, version=2):
    
    '''
    check whether html contains postform/user name input field/ password input field
    :param x: Tuple object (len(forms):int, methods:List[str|float], count_inputs:List[int], count_password:List[int], count_username:List[int])
    :return:
    '''

    num_form, methods, num_inputs, num_password, num_username = x
#     print(num_password, num_username)
    
    if len(methods) == 0:
        have_postform = 0
    else:
        have_postform = (len([y for y in [x for x in methods if x is not None] if y.lower() == 'post']) > 0)

    if len(num_password) == 0:
        have_password = 0
    else:
        have_password = (np.sum(num_password) > 0)

    if len(num_username) == 0:
        have_username = 0
    else:
        have_username = (np.sum(num_username) > 0)

    # CRP = 0, nonCRP = 1
    if version == 1:
        return 0 if (have_postform) else 1
    elif version == 2:
        return 0 if (have_password | have_username) else 1
    elif version == 3:
        return 0 if (have_postform | have_password | have_username) else 1