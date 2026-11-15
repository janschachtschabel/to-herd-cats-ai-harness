import type { UseFormReturn } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Field } from '@/features/shared/forms'
import { secretModes, type ProviderValues } from './providerForm'

/** The fields of a sign-in provider. Google's issuer and scopes are fixed by the preset;
 *  the key never changes once created; the secret is only ever written. */
export function ProviderFields({
  form,
  creating = false,
  secretSet = false,
}: {
  form: UseFormReturn<ProviderValues>
  creating?: boolean
  secretSet?: boolean
}) {
  const { t } = useTranslation()
  const errors = form.formState.errors
  const kind = form.watch('kind')
  const mode = form.watch('secretMode')
  const signup = form.watch('allow_signup')
  const generic = kind === 'generic'
  return (
    <>
      {generic && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label={t('oidcAdmin.form.key')}
            hint={t('oidcAdmin.form.keyHint')}
            error={errors.key?.message}
          >
            {(props) => (
              <Input
                {...props}
                autoFocus={creating}
                disabled={!creating}
                autoComplete="off"
                {...form.register('key')}
              />
            )}
          </Field>
          <Field
            label={t('oidcAdmin.form.name')}
            hint={t('oidcAdmin.form.nameHint')}
            error={errors.name?.message}
          >
            {(props) => <Input {...props} {...form.register('name')} />}
          </Field>
        </div>
      )}
      {generic && (
        <Field label={t('oidcAdmin.form.issuer')} error={errors.issuer?.message}>
          {(props) => (
            <Input
              {...props}
              type="url"
              inputMode="url"
              placeholder={t('oidcAdmin.form.issuerPlaceholder')}
              {...form.register('issuer')}
            />
          )}
        </Field>
      )}
      <Field label={t('oidcAdmin.form.clientId')} error={errors.client_id?.message}>
        {(props) => (
          <Input
            {...props}
            autoFocus={creating && !generic}
            autoComplete="off"
            {...form.register('client_id')}
          />
        )}
      </Field>
      <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
        <legend className="px-1 text-sm font-medium">{t('oidcAdmin.form.secret')}</legend>
        {!creating && (
          <p className="text-xs text-muted-foreground">
            {secretSet ? t('oidcAdmin.secretStored') : t('oidcAdmin.secretMissing')}
          </p>
        )}
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {secretModes(kind, creating).map((value) => (
            <label key={value} className="inline-flex items-center gap-1.5 text-sm">
              <input type="radio" value={value} {...form.register('secretMode')} />
              {t(`oidcAdmin.form.secretModes.${value}`)}
            </label>
          ))}
        </div>
        {mode === 'value' && (
          <Field
            label={t('oidcAdmin.form.secretValue')}
            hint={t('oidcAdmin.form.secretValueHint')}
            error={errors.secretValue?.message}
          >
            {(props) => (
              <Input
                {...props}
                type="password"
                autoComplete="new-password"
                {...form.register('secretValue')}
              />
            )}
          </Field>
        )}
        {mode === 'env' && (
          <Field label={t('oidcAdmin.form.secretEnv')} error={errors.secretEnv?.message}>
            {(props) => (
              <Input
                {...props}
                autoComplete="off"
                placeholder={t('oidcAdmin.form.secretEnvPlaceholder')}
                {...form.register('secretEnv')}
              />
            )}
          </Field>
        )}
      </fieldset>
      {generic && (
        <>
          <Field label={t('oidcAdmin.form.scopes')} error={errors.scopes?.message}>
            {(props) => <Input {...props} autoComplete="off" {...form.register('scopes')} />}
          </Field>
          <Check
            label={t('oidcAdmin.form.trustEmail')}
            hint={t('oidcAdmin.form.trustEmailHint')}
            {...form.register('trust_email')}
          />
        </>
      )}
      <Check
        label={t('oidcAdmin.form.allowSignup')}
        hint={t('oidcAdmin.form.allowSignupHint')}
        {...form.register('allow_signup')}
      />
      <Field
        label={t('oidcAdmin.form.domains')}
        hint={t('oidcAdmin.form.domainsHint')}
        error={errors.domains?.message}
      >
        {(props) => (
          <Textarea
            {...props}
            rows={3}
            placeholder={signup ? t('oidcAdmin.form.domainsPlaceholder') : undefined}
            {...form.register('domains')}
          />
        )}
      </Field>
      <Check label={t('oidcAdmin.form.enabled')} {...form.register('enabled')} />
    </>
  )
}

/** A checkbox with its label and an optional hint below. */
function Check({
  label,
  hint,
  ...input
}: { label: string; hint?: string } & React.ComponentProps<'input'>) {
  return (
    <div className="flex flex-col gap-1">
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" {...input} />
        {label}
      </label>
      {hint && <p className="ps-6 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}
