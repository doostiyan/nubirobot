# اعتبار ریالی

## احراز هویت
فرایند احرازهویت با استفاده از رمزنگاری نامتقارن پیاده سازی شده است. لذا به منظور دسترسی به APIهای مشروحه در این سند میبایست بدنه درخواست خود را با استفاده از کلید خصوصی رمزنگاری کرده و به همراه درخواست ارسال کنید.
ارسال این امضاء در Header درخواست و از طریق کلید x-request-signature صورت میگیرد.

## رمزنگاری درخواست
نحوه امضاء کردن بدنه درخواست نیز به منظور جلوگیری از هرگونه تفاوت در ترتیب پارامترهای بدنه و ... به شرح ذیل انجام می‌گیرد.
مقادیر پارامترهای درخواست به ترتیب حروف الفبا و جداشده با پایپ ساین (pipe)
به عنوان مثال: برای ارسال درخواست قفل کردن وثیقه به مقدار مشخص (lock) می‌بایست مقادیر پارامترهای لازم به این صورت امضا گردد:

پارامترها به ترتیب حروف الفبا
  - amount|planType|nationalCode|trackId

مقادیر نمونه و متن نهایی جهت رمزنگاری
  - 100000|credit|0923000000|a824aa66-0fd7-4a7d-a1be-8c5610c72fb7

  * ```python
    import requests
    import base64
    from Crypto.PublicKey import RSA
    from Crypto.Signature import PKCS1_v1_5
    from Crypto.Hash import SHA256

    # Replace these variables with your actual values
    base_url = "<replace_with_base_url>"
    private_key_path = "path/to/your/private_key.pem"  # Replace with the path to your private key file

    # Prepare the payload
    payload = {
        "trackId": "a824aa66-0fd7-4a7d-a1be-8c5610c72fb7",
        "planType": "credit",
        "nationalCode": "0923000000",
        "amount": "100000"
    }

    # Sort the payload values alphabetically
    sorted_values = sorted(payload.values())

    # Concatenate values with a pipe sign ('|')
    message = '|'.join(map(str, sorted_values))

    # Hash the message with SHA-256
    hashed_message = SHA256.new(message.encode('utf-8'))

    # Load private key
    with open(private_key_path, "rb") as key_file:
        private_key = RSA.import_key(key_file.read())

    # Sign the hashed message with PKCS1_v1_5
    signer = PKCS1_v1_5.new(private_key)
    signature = signer.sign(hashed_message)

    # Convert the signature to base64
    signature_base64 = base64.b64encode(signature).decode('utf-8')

    # Send the POST request
    url = f"{base_url}/collateral/v1/lock"
    headers = {
        "Content-Type": "application/json",
        "X-REQUEST-SIGNATURE": signature_base64
    }

    response = requests.post(url, json=payload, headers=headers)

    # Print the response
    print(response.status_code)
    print(response.text)
    ```

## نکات و ملاحظات
با توجه به اینکه دسترسی به APIهای فراهم شده صرفا محدود به IPهای white شده می‌باشد. لذا در صورتی که درخواست از IPهایی که در Whitelist موجود نیستند ارسال گردد با خطای 404 مواجه خواهند بود.

## اندپوینت‌ها

### استعلام از وثیقه
  بررسی وثیقه‌ی موجود کاربر به جهت دریافت وام، اعتبار یا دبیت. با ارسال طرح مورد نظر و مشخص کردن کاربر، سقف مبلغی را که کاربر میتواند اعتبار یا وام بگیرد را دریافت خواهد کرد.
  در صورتی که کاربر وثیقه‌ای نداشته باشد مقدار بازگشتی صفر خواهد بود.
  * **POST /collateral/v1/estimate**
    ----

    * **URL Params**
      None
    * **Data Params**
      * ```json
        {
          "planType": "<str:plan>",
          "nationalCode": "<str:national_code>"
        }
        ```
      <div dir="rtl" align="right">
          <ul>
              <li dir="rtl" >planType: یکی از مقادیر موجود در enum: Plans باید باشد.</li>
          </ul>
      </div>
    * **Headers**
      * Content-Type: application/json
      * X-REQUEST-SIGNATURE: signed "amount|nationalCode" with private-key
    * **Success Response:**
      * **Code:** 200 OK
      * **Content:**
        ```json
        {
          "status": "ok",
          "amount": "<str:amount>"
        }
        ```

      * **Code:** 404 Not Found
        - در صورتی که کاربر سرویس فعال نداشته باشد یا اصلا جزو کاربران ما نباشد این پاسخ ارسال خواهد شد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "UserNotFound",
          "message": "User not found!"
        }
        ```

      * **Code:** 429 Too Many Requests
        - در صورتی که تعداد درخواست ارسالی شما از نرخ مشخص شده در توضیحات بیشتر باشد، با این پاسخ روبرو خواهید بود
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "TooManyRequest",
          "message": "Too many request"
        }
        ```

      * **Code:** 401 Unauthorized
        - فرایند احراز هویت مورد تایید نمی باشد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "AuthorizationError",
          "message": "The signature is not valid!"
        }
        ```

      * **Code:** 404 Not Found
        - IP شما جزو مجموعه‌ی IPهای امن مشخص شده نمی‌باشد
      * **Content:**
        None

      * **Code:** 400 Bad Request
        - فرمت کد ملی ارسالی اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "The NationalCode is not valid! It should be a 10-character string."
        }
        ```

      * **Code:** 400 Bad Request
        - طرح ارسال نشده یا اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "The PlanType is not valid!"
        }
        ```
    * **Sample**
      * ```curl
        curl -X POST \
        <replace_with_base_url>/collateral/v1/eligibility \
        -H "Content-Type: application/json" \
        -H "X-REQUEST-SIGNATURE: <signed_body_with_private-key>" \
        -d '{
          "nationalCode": "<replace_with_national_code>",
          "planType": "credit"
        }'
        ```

### قفل کردن وثیقه
قفل کردن مقداری مشخص از وثیقه کاربر

  * **POST /collateral/v1/lock**
    ----

    * **URL Params**
      None
    * **Data Params**
      * ```json
        {
          "trackId": "<uuid:track_id>",
          "planType": "<str:plan>",
          "nationalCode": "<str:national_code>",
          "amount": "<str:amount>"
        }
        ```
      <div dir="rtl" align="right">
          <ul>
              <li dir="rtl" >amount: به صورت ریالی در نظر گرفته شده است.</li>
              <li dir="rtl" >planType: یکی از مقادیر موجود در enum: Plans باید باشد.</li>
          </ul>
      </div>
    * **Headers**
      * Content-Type: application/json
      * X-REQUEST-SIGNATURE: signed "amount|planType|nationalCode|trackId" with private-key
    * **Success Response:**
      * **Code:** 200 OK
      * **Content:**
        ```json
        {
          "status": "ok"
        }
        ```
    * **Error Response:**
      * **Code:** 402 Payment Required
        - دارایی کاربر کمتر از مقدار مشخص شده برای قفل کردن به عنوان وثیقه می‌باشد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "InsufficientBalance",
          "message": "Amount cannot exceed active balance"
        }
        ```

      * **Code:** 404 Not Found
        - در صورتی که کاربر سرویس فعال نداشته باشد یا اصلا جزو کاربران ما نباشد این پاسخ ارسال خواهد شد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "UserNotFound",
          "message": "User not found!"
        }
        ```

      * **Code:** 409 Conflict
        - درخواست تکراری می‌باشد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "DuplicateRequestError",
          "message": "The request is duplicated!"
        }
        ```

      * **Code:** 429 Too Many Requests
        - در صورتی که تعداد درخواست ارسالی شما از نرخ مشخص شده در توضیحات بیشتر باشد، با این پاسخ روبرو خواهید بود
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "TooManyRequest",
          "message": "Too many request"
        }
        ```

      * **Code:** 401 Unauthorized
        - فرایند احراز هویت مورد تایید نمی باشد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "AuthorizationError",
          "message": "The signature is not valid!"
        }
        ```

      * **Code:** 404 Not Found
        - IP شما جزو مجموعه‌ی IPهای امن مشخص شده نمی‌باشد
      * **Content:**
        None

      * **Code:** 400 Bad Request
        - فرمت کد ملی ارسالی اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "The NationalCode is not valid! It should be a 10-character string."
        }
        ```

      * **Code:** 400 Bad Request
        - طرح ارسال نشده یا اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "The PlanType is not valid!"
        }
        ```

      * **Code:** 400 Bad Request
        - فرمت شناسه درخواست trackId اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "trackId is not valid! It should be in uuid format"
        }
        ```

      * **Code:** 400 Bad Request
        - فرمت مبلغ ارسالی اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "amount is not valid!"
        }
        ```
    * **Sample**
      * ```curl
        curl -X POST \
        <replace_with_base_url>/collateral/v1/lock \
        -H "Content-Type: application/json" \
        -H "X-REQUEST-SIGNATURE: <signed_body_with_private-key>" \
        -d '{
          "trackId": "<replace_with_uuid>",
          "planType": "credit",
          "nationalCode": "<replace_with_national_code>",
          "amount": "50000"
        }'
        ```

### آزادسازی وثیقه
آزادسازی مقداری مشخص از دارایی قفل شده‌ی کاربر

  * **POST /collateral/v1/unlock**
    ----

    * **URL Params**
      None
    * **Data Params**
      * ```json
        {
          "trackId": "<uuid:track_id>",
          "planType": "<str:plan>",
          "nationalCode": "<str:national_code>",
          "amount": "<str:amount>"
        }
        ```
      <div dir="rtl" align="right">
          <ul>
              <li dir="rtl" >amount: به صورت ریالی در نظر گرفته شده است.</li>
              <li dir="rtl" >planType: یکی از مقادیر موجود در enum: Plans باید باشد.</li>
          </ul>
      </div>
    * **Headers**
      * Content-Type: application/json
      * X-REQUEST-SIGNATURE: signed "amount|planType|nationalCode|trackId" with private-key
    * **Success Response:**
      * **Code:** 200 OK
      * **Content:**
        ```json
        {
          "status": "ok"
        }
        ```
    * **Error Response:**
      * **Code:** 422 Unprocessable Content
      - در صورتی که وثیقه کاربر به اندازه‌ی کافی نباشد این پاسخ را خواهید داشت
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "InappropriateAmount",
          "message": "The user has more debt that the amount!"
        }
        ```

      * **Code:** 404 Not Found
        - در صورتی که کاربر سرویس فعال نداشته باشد یا اصلا جزو کاربران ما نباشد این پاسخ ارسال خواهد شد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "UserNotFound",
          "message": "User not found!"
        }
        ```

      * **Code:** 409 Conflict
        - درخواست تکراری می‌باشد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "DuplicateRequestError",
          "message": "The request is duplicated!"
        }
        ```

      * **Code:** 429 Too Many Requests
        - در صورتی که تعداد درخواست ارسالی شما از نرخ مشخص شده در توضیحات بیشتر باشد، با این پاسخ روبرو خواهید بود
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "TooManyRequest",
          "message": "Too many request"
        }
        ```

      * **Code:** 401 Unauthorized
        - فرایند احراز هویت مورد تایید نمی باشد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "AuthorizationError",
          "message": "The signature is not valid!"
        }
        ```

      * **Code:** 404 Not Found
        - IP شما جزو مجموعه‌ی IPهای امن مشخص شده نمی‌باشد
      * **Content:**
        None

      * **Code:** 400 Bad Request
        - فرمت کد ملی ارسالی اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "The NationalCode is not valid! It should be a 10-character string."
        }
        ```

      * **Code:** 400 Bad Request
        - طرح ارسال نشده یا اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "The PlanType is not valid!"
        }
        ```

      * **Code:** 400 Bad Request
        - فرمت شناسه درخواست trackId اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "trackId is not valid! It should be in uuid format"
        }
        ```

      * **Code:** 400 Bad Request
        - فرمت مبلغ ارسالی اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "amount is not valid!"
        }
        ```
    * **Sample**
      * ```curl
        curl -X POST \
        <replace_with_base_url>/collateral/v1/unlock \
        -H "Content-Type: application/json" \
        -H "X-REQUEST-SIGNATURE: <signed_body_with_private-key>" \
        -d '{
          "trackId": "<replace_with_uuid>",
          "planType": "Silver",
          "nationalCode": "<replace_with_national_code>",
          "amount": "20000"
        }'
        ```

### تسویه
ارسال مقدار ریالی مورد نیاز جهت تسویه
  * **POST /collateral/v1/settle**
    ----

    * **URL Params**
      None
    * **Data Params**
      * ```json
        {
          "trackId": "<uuid:track_id>",
          "planType": "<str:plan>",
          "nationalCode": "<str:national_code>",
          "amount": "<str:amount>"
        }
        ```
      <div dir="rtl" align="right">
          <ul>
              <li dir="rtl" >amount: به صورت ریالی در نظر گرفته شده است.</li>
              <li dir="rtl" >planType: یکی از مقادیر موجود در enum: Plans باید باشد.</li>
          </ul>
      </div>
    * **Headers**
      * Content-Type: application/json
      * X-REQUEST-SIGNATURE: signed "amount|planType|nationalCode" with private-key
    * **Success Response:**
      * **Code:** 200 OK
      * **Content:**
        ```json
        {
          "status": "ok"
        }
        ```
    * **Error Response:**
      * **Code:** 422 Unprocessable Content
      - در صورتی که وثیقه کاربر به اندازه‌ی کافی نباشد این پاسخ را خواهید داشت
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "InappropriateAmount",
          "message": "The user has more debt than the amount!"
        }
        ```

      * **Code:** 404 Not Found
        - در صورتی که کاربر سرویس فعال نداشته باشد یا اصلا جزو کاربران ما نباشد این پاسخ ارسال خواهد شد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "UserNotFound",
          "message": "User not found!"
        }
        ```

      * **Code:** 409 Conflict
        - درخواست تکراری می‌باشد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "DuplicateRequestError",
          "message": "The request is duplicated!"
        }
        ```

      * **Code:** 423 Locked
        - عملیات دیگری در حال اجرا است! دقایقی بعد مجددا امتحان کنید
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "SettlementError",
          "message": "Another settlement process is running!"
        }
        ```

      * **Code:** 429 Too Many Requests
        - در صورتی که تعداد درخواست ارسالی شما از نرخ مشخص شده در توضیحات بیشتر باشد، با این پاسخ روبرو خواهید بود
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "TooManyRequest",
          "message": "Too many request"
        }
        ```

      * **Code:** 401 Unauthorized
        - فرایند احراز هویت مورد تایید نمی باشد
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "AuthorizationError",
          "message": "The signature is not valid!"
        }
        ```

      * **Code:** 404 Not Found
        - IP شما جزو مجموعه‌ی IPهای امن مشخص شده نمی‌باشد
      * **Content:**
        None

      * **Code:** 400 Bad Request
        - فرمت کد ملی ارسالی اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "The NationalCode is not valid! It should be a 10-character string."
        }
        ```

      * **Code:** 400 Bad Request
        - طرح ارسال نشده یا اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "The PlanType is not valid!"
        }
        ```

      * **Code:** 400 Bad Request
        - فرمت شناسه درخواست trackId اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "trackId is not valid! It should be in uuid format"
        }
        ```

      * **Code:** 400 Bad Request
        - فرمت مبلغ ارسالی اشتباه است
      * **Content:**
        ```json
        {
          "status": "failed",
          "code": "ValidationError",
          "message": "amount is not valid!"
        }
        ```
    * **Sample**
      * ```curl
        curl -X POST \
        <replace_with_base_url>/collateral/v1/settle \
        -H "Content-Type: application/json" \
        -H "X-REQUEST-SIGNATURE: <signed_body_with_private-key>" \
        -d '{
          "trackId": "<replace_with_uuid>",
          "planType": "credit",
          "nationalCode": "<replace_with_national_code>",
          "amount": "15000"
        }'
        ```

## Enums
### Plans

- credit
- loan
- debit
