# REST File Command

A Home Assistant custom integration to upload files to a RESTful API endpoint. This integration is a clone of [RESTful Command](https://github.com/home-assistant/core/tree/dev/homeassistant/components/rest_command) with minor modifications.

## Features

-   Upload files to REST APIs using `multipart/form-data`.
-   Supports templated URLs, headers, file names, and additional form fields.
-   Specify a custom field name for the uploaded file (default: `file`).
-   Dynamically override file name and form fields in service calls using templates.
-   Supports basic HTTP authentication.
-   Configurable request timeout (default: 10 seconds).
-   Verifies SSL certificates by default (optional).
-   Stores the last response and status code in a variable if requested.

## 📦Installation📦

### HACS (Recommended)

1. Open HACS
1. Go to _Integrations_
1. Click the ellipse button in the top right and select _Custom Repositories_
1. Enter the following information
    - _Repository_: `https://github.com/amura11/ha-rest-file-command`
    - _Category_: `Integration`
1. Click "Add"
1. Close the modal then click _Explore & Download Repositories_
1. Search for `Secret Checker`` and select the repository
1. Click the _Download_ button
1. Configure your command(s)
1. Restart Home Assistant

### Manually

1. Using the tool of choice open the directory (folder) for your HA configuration (where you find `configuration.yaml`).
1. If you do not have a `custom_components` directory (folder) there, you need to create it.
1. In the `custom_components` directory (folder) create a new folder called `rest-file-command`.
1. Download _all_ the files from the `custom_components/rest-file-command/` directory (folder) in this repository.
1. Place the files you downloaded in the new directory (folder) you created.
1. Configure your command(s)
1. Restart Home Assistant

## 🔧Configuration🔧

| Name              | Type    | Description                                                                      | Required | Default |
| ----------------- | ------- | -------------------------------------------------------------------------------- | -------- | ------- |
| `url`             | string  | The URL (supports template) for sending request.                                 | ✔        |         |
| `method`          | string  | HTTP method to use (e.g., `post`, `get`, etc.).                                  |          | `post`  |
| `headers`         | map     | The headers for the requests (supports templates).                               |          |         |
| `username`        | string  | The username for basic HTTP authentication (digest is not supported).            |          |         |
| `password`        | string  | The password for basic HTTP authentication (digest is not supported).            |          |         |
| `timeout`         | number  | Timeout for requests in seconds.                                                 |          | `10`    |
| `content_type`    | string  | Content type for the request.                                                    |          |         |
| `verify_ssl`      | boolean | Verify the SSL certificate of the endpoint.                                      |          | `true`  |
| `file_name`       | string  | Default filename to send (supports template). Can be overridden in service call. |          |         |
| `form_field_name` | string  | The name to use for the file in the form data.                                   |          | `file`  |
| `form_data`       | map     | Addition form data to be sent in the multipart form (supports templates).        |          |         |

### Example

**Basic**

```yaml
rest_file_command:
    do_the_thing:
        url: "http://example.tld:8181/do-thing"
        method: put
        content_type: "application/x-www-form-urlencoded"
        timeout: 5
```

**Kitchen Sink**

```yaml
rest_file_command:
    do_the_thing:
        url: "https://example.com/upload/{{ device_id }}"
        method: post
        timeout: 15
        content_type: "application/octet-stream"
        verify_ssl: true
        headers:
            X-Device-ID: "{{ device_id }}"
        username: !secret api_user
        password: !secret api_password
        file_name: "snapshot_{{ now().strftime('%Y%m%d_%H%M%S') }}.jpg"
        form_field_name: "snapshot_file"
        form_data:
            description: "Snapshot taken at {{ now().isoformat() }}"
            user_id: "{{ user_id }}"
```

## 📄Usage📄

Calling the configured command(s):

| Name                | Type   | Description                                                                | Required |
| ------------------- | ------ | -------------------------------------------------------------------------- | -------- |
| `file`              | string | Path to the file to upload.                                                | ✔        |
| `file_name`         | string | Override for filename sent in the multipart form data (supports template). |          |
| `form_data`         | map    | Addition form data to be sent in the multipart form (supports templates).  |          |
| `response_variable` | string | The name of the variable to put the response into.                         |          |

If `response_variable` is defined, the response from the server will be put in a variable with the following format:

```json
{
    status: <HTTP Status Code>,
    content: <Response Content>
}
```

### Example

```yaml
- service: rest_file_command.do_the_thing
  response_variable: upload_response
  data:
      file: /config/www/image.jpg
- choose:
      - conditions:
            - condition: template
              value_template: "{{ upload_response['status'] == 200 }}"
        sequence:
            - service: notify.mobile_app_iphone
              data:
                  title: "File uploaded"
                  message: "Returned link: {{ upload_response['url'] }}"
```
