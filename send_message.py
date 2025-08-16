from send_slack_message import send_slack_message
from gdocs import copy_document_and_edit
from replacements import replace_recursive


def send_message(
    channel,
    content,
    id='No_ID',
    replacements=None,
    google_doc=None
):
    print(f"Sending message: {id}")

    if replacements is None:
        replacements = {}

    # Ensure all replacement keys have curly brackets
    replacements = {'{' + k.strip('{').strip('}') + '}':v for k, v in replacements.items()}
    replacements = replace_recursive(replacements)

    if google_doc is not None:
        google_doc = replace_recursive(google_doc, replacements)
        new_doc_id, new_doc_url = copy_document_and_edit(
            **google_doc, replacements=replacements
        )
        if new_doc_url:
            replacements['{google_doc}'] = new_doc_url
        else:
            raise RuntimeError('google doc url not generated')
    
    content = replace_recursive(content, replacements)

    app = channel.pop('app')
    if app == 'slack':
        send_slack_message(
            **channel,
            **content
        )


if __name__ == '__main__':

    import yaml

    # Load messages
    with open('config.yaml', 'r') as file:
        messages = yaml.safe_load(file)['messages']

    test_messages = [messages[0]]

    for test_message in test_messages:

        schedule = test_message.pop('schedule')
        enabled = test_message.pop('enabled')

        if enabled:
            send_message(**test_message)