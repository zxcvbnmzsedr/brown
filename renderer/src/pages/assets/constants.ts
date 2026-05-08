export interface BucketFormState {
  name: string
  targetWeight: string
  displayOrder: string
}

export const emptyBucketForm: BucketFormState = {
  name: '',
  targetWeight: '25',
  displayOrder: '0',
}

export interface GroupFormState {
  bucketId: string
  name: string
  targetWeight: string
  displayOrder: string
}

export const emptyGroupForm: GroupFormState = {
  bucketId: '',
  name: '',
  targetWeight: '0',
  displayOrder: '0',
}
