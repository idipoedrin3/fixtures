from utilities.email_service import send_email_task


class EmailClient:
    @staticmethod
    def send(
        subject,
        recipients,
        template_html,
        template_txt=None,
        context=None,
        attachments=None,
    ):
        if isinstance(recipients, str):
            recipients = [recipients]

        send_email_task.delay(
            subject=subject,
            recipients=recipients,
            template_html=template_html,
            template_txt=template_txt,
            context=context,
            attachments=attachments,
        )
