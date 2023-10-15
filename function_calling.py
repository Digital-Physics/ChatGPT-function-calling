import openai
import json
from dotenv import find_dotenv, load_dotenv # for api key
import os
import pandas as pd

# print("load api key")
load_dotenv(find_dotenv())

# print("assign the key to openai.api_key")
openai.api_key = os.getenv("OPENAI_API_KEY")

# print("read the actuarial csv table downloaded from the Society of Actuaries website")
df = pd.read_csv("mortality_table.csv", sep=',', skiprows=24, header=None, names=['Age','Value']) 
q_x = df['Value'].tolist()
# print("Add ages 0-4 since the actuarial mortality table starts at 5. Now each index in q_x will correspond to the probability of dying in the next one year period starting at age x. The list now contatins ages 0 to 110.")
q_x = [q_x[0] for i in range(5)] + q_x
p_x = [1 - q_x[age] for age in range(len(q_x))] # survival prob

# print("define a helper function for computing t_p_x, the probability someone age x survives t years, and t_q_x, the prob someone age x survives t-1 years and dies in the following year.")
def generate_actuarial_factors_over_t_years(list_of_p_x):
    """Calculate probabilities related to surviving t years and prob of surviving t-1 years and then dying"""

    p = 1 # initialize the prob of survival to time t = 0
    # the first index we care about in these lists is t = 1, but we don't want this value in Python's index 0 (not 1), so we initialize the first elements in the lists for t = 0
    t_p_x = [1] 
    t_q_x = [0]

    for p_x in list_of_p_x:
        t_q_x.append(p*(1 - p_x))
        p *= p_x
        t_p_x.append(p)

    return t_p_x, t_q_x

def get_present_value_of_annuity(amount, age, interest_rate):
    """Calculate the present value of an annual annuity."""

    t_p_x, _ = generate_actuarial_factors_over_t_years(p_x[age: len(p_x)])
    expected_cash_flows = [(amount*prob_survival)*((1 + interest_rate)**-t) for t, prob_survival in enumerate(t_p_x)]

    present_value = sum(expected_cash_flows)

    present_value_info = {
        "present_value": present_value,
    }
    return json.dumps(present_value_info)

def get_present_value_of_death_benefit(amount, age, interest_rate):
    """Calculate the present value of a death benefit."""

    _, t_q_x = generate_actuarial_factors_over_t_years(p_x[age: len(p_x)])
    expected_cash_flows = [(amount*prob_survival_and_then_death)*((1 + interest_rate)**-t) for t, prob_survival_and_then_death in enumerate(t_q_x)]

    present_value = sum(expected_cash_flows)

    present_value_info = {
        "present_value": present_value,
    }
    return json.dumps(present_value_info)

def answer_question_with_function_calling(query):
    # Step 1: send the conversation and available functions to GPT
    messages = [
        {"role": "user", "content": query},
        ]
    functions = [
        {
            "name": "get_present_value_of_annuity",
            "description": "Get the present value of an annual annuity payment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "This is the annual annuity payment amount."
                    },
                    "age": {
                        "type": "number",
                        "description": "This is the annuitant's age."
                    },
                    "interest_rate": {
                        "type": "number",
                        "description": "This is the annual interest rate as a decimal used to discount annual annuity payments. e.g. 5 percent is 0.05"
                    },
                },
                "required": ["amount", "age", "interest_rate"],
            },
        },

        {
            "name": "get_present_value_of_death_benefit",
            "description": "Get the present value of a life insurance death benefit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "This is the death benefit payment amount."
                    },
                    "age": {
                        "type": "number",
                        "description": "This is the insured's age."
                    },
                    "interest_rate": {
                        "type": "number",
                        "description": "This is the annual interest rate as a decimal used to discount the death benefit amout. e.g. 5 percent is 0.05"
                    },
                },
                "required": ["amount", "age", "interest_rate"],
            },
        }
    ]

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-0613", #not all models have function calling ability but this one does
        messages=messages,
        functions=functions,
        function_call="auto",  # guess whether you should use the provided functions
    )
   
    response_message = response["choices"][0]["message"]

    # Step 2: check if GPT wanted to call a function
    if response_message.get("function_call"):
        # Step 3: call the function
        # Note: the JSON response may not always be valid; be sure to handle errors
        available_functions = {
            "get_present_value_of_annuity": get_present_value_of_annuity,
            "get_present_value_of_death_benefit": get_present_value_of_death_benefit,
        }  
        function_name = response_message["function_call"]["name"]
        function_to_call = available_functions[function_name]
        function_args = json.loads(response_message["function_call"]["arguments"])
        # print("using these params: ", function_args.get("amount"), function_args.get("age"), function_args.get("interest_rate"))
        # print("to run this function: ", function_name)
        function_response = function_to_call(
            amount=function_args.get("amount"),
            age=function_args.get("age"),
            interest_rate=function_args.get("interest_rate"),
        )

        # Step 4: send the info on the function call and function response to GPT
        messages.append(response_message)  # extend conversation with assistant's reply
        messages.append(
            {
                "role": "function",
                "name": function_name,
                "content": function_response,
            }
        )  # extend conversation with function response
        second_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages,
        )  # get a new natural language response from GPT where it can see the original question, the function called with params in parsed, and the function response which shows the computation's answer
        
        print(second_response["choices"][0]["message"]["content"])
        return second_response

def get_input_and_answer_question():
    query = input('Do you have an annuity or life insurance death benefit valuation question?: ')
    answer_question_with_function_calling(query)
    print()

while True:
    get_input_and_answer_question()